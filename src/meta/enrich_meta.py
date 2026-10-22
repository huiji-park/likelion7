"""카탈로그 2,364표 getMeta 보강 -> data/processed/table_meta.jsonl, obj_values/<org>_<tbl>.json

재개 가능: meta_ok=true 인 표는 건너뛰고, 실패 표만 재시도한다. HTTP 응답은 data/cache/ 에 캐시된다.
send_de 는 statisticsList(getList, parentListId=카탈로그 list_id) 응답의 SEND_DE.
실행: python -m src.meta.enrich_meta [--limit N] [--retry-failed]
키는 KOSIS_API_KEY / KOSIS_ENV_PATH (src.kosis.client.get_key).
"""
import json
import sys
import time
from math import prod
from pathlib import Path

from src.kosis.client import Kosis, KosisError, mask

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
CATALOG = PROC / "population_table_catalog.jsonl"
OUT = PROC / "table_meta.jsonl"
OBJ_DIR = PROC / "obj_values"


def build(org, tbl, itm):
    objs, items = {}, []
    for r in itm:
        if r.get("OBJ_ID") == "ITEM":
            items.append({"id": r["ITM_ID"], "nm": r["ITM_NM"], "unit": r.get("UNIT_NM") or "", "unit_id": r.get("UNIT_ID") or ""})
        else:
            o = objs.setdefault(r["OBJ_ID"], {"sn": int(r.get("OBJ_ID_SN") or 0), "nm": r["OBJ_NM"], "vals": []})
            o["vals"].append({"code": r["ITM_ID"], "nm": r["ITM_NM"], "up": r.get("UP_ITM_ID") or ""})
    ordered = sorted(objs.values(), key=lambda o: o["sn"])
    obj_names = [o["nm"] for o in ordered]
    obj_sizes = [len(o["vals"]) for o in ordered]
    units = sorted({i["unit"] for i in items if i["unit"]})
    meta = {
        "org_id": org, "tbl_id": tbl, "meta_ok": True,
        "n_obj": len(ordered), "obj_names": obj_names, "obj_sizes": obj_sizes,
        "items": items, "n_items": len(items), "units": units,
        "est_cells_per_period": prod(obj_sizes) * max(len(items), 1),
    }
    values = {f"objL{n}": o["vals"] for n, o in enumerate(ordered, 1)}
    return meta, values


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    cat = [json.loads(l) for l in open(CATALOG, encoding="utf-8")]
    prev = {}
    if OUT.exists():
        for l in open(OUT, encoding="utf-8"):
            m = json.loads(l)
            prev[(m["org_id"], m["tbl_id"])] = m
    todo = [c for c in cat if not prev.get((c["org_id"], c["tbl_id"]), {}).get("meta_ok")]
    if limit:
        todo = todo[:limit]
    OBJ_DIR.mkdir(parents=True, exist_ok=True)
    k = Kosis()
    send_cache = {}

    def send_de(c):
        lid = c["paths"][0]["list_id"]
        if lid not in send_cache:
            try:
                send_cache[lid] = {x["TBL_ID"]: x.get("SEND_DE") for x in k.list("MT_ZTITLE", lid) if x.get("TBL_ID")}
            except Exception:
                send_cache[lid] = {}
        return send_cache[lid].get(c["tbl_id"])

    t0, ok, fail = time.time(), 0, 0
    for i, c in enumerate(todo, 1):
        org, tbl = c["org_id"], c["tbl_id"]
        try:
            itm = k.meta(org, tbl, "ITM")
            if not isinstance(itm, list) or not itm:
                raise KosisError("EMPTY", "ITM 응답이 비어 있음")
            meta, values = build(org, tbl, itm)
            meta["send_de"] = send_de(c)
            (OBJ_DIR / f"{org}_{tbl}.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
            ok += 1
        except Exception as e:
            err = e.err if isinstance(e, KosisError) else type(e).__name__
            meta = {"org_id": org, "tbl_id": tbl, "meta_ok": False, "error": str(err), "error_msg": mask(e)[:300],
                    "n_obj": 0, "obj_names": [], "obj_sizes": [], "items": [], "n_items": 0, "units": [],
                    "est_cells_per_period": 0, "send_de": None}
            fail += 1
        prev[(org, tbl)] = meta
        if i % 25 == 0:
            print(f"{i}/{len(todo)} ok={ok} fail={fail} {time.time()-t0:.0f}s", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for c in cat:
            m = prev.get((c["org_id"], c["tbl_id"]))
            if m:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"DONE ok={ok} fail={fail} {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
