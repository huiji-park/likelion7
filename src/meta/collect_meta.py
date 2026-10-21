"""Step 2: per-table meta via statisticsData.do?method=getMeta (type=TBL, PRD, ITM).

Resumable: finished tables are appended to data/raw/meta_compact.jsonl (skipped on rerun);
HTTP responses are cached in data/cache/. Failures -> data/raw/meta_errors.jsonl.
Compaction: ITM rows are split into classification objects (OBJ_ID_SN = objL index) and items.
Usage: .venv/Scripts/python.exe -m src.meta.collect_meta [--limit N]
"""
import json
import sys
import time
from collections import OrderedDict
from pathlib import Path

from src.kosis.client import Kosis, KosisError, mask

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = RAW / "meta_compact.jsonl"
ERR = RAW / "meta_errors.jsonl"
MAX_VALUES_KEPT = 400  # classification value names kept per object (full count stored separately)


def compact(org, tbl, tb, prd, itm):
    objs = OrderedDict()
    items = []
    for r in itm:
        if r.get("OBJ_ID") == "ITEM":
            items.append({"id": r["ITM_ID"], "nm": r["ITM_NM"], "unit": r.get("UNIT_NM"), "unit_id": r.get("UNIT_ID")})
        else:
            key = r["OBJ_ID"]
            o = objs.setdefault(key, {"obj_id": key, "sn": r.get("OBJ_ID_SN"), "nm": r["OBJ_NM"], "n": 0, "values": [], "top": 0})
            o["n"] += 1
            if not r.get("UP_ITM_ID"):
                o["top"] += 1
            if len(o["values"]) < MAX_VALUES_KEPT:
                o["values"].append([r["ITM_ID"], r["ITM_NM"], r.get("UP_ITM_ID")])
    return {
        "org_id": org, "tbl_id": tbl,
        "tbl_nm": (tb[0].get("TBL_NM") if tb else None),
        "tbl_nm_eng": (tb[0].get("TBL_NM_ENG") if tb else None),
        "prd": [{"se": p.get("PRD_SE"), "start": p.get("STRT_PRD_DE"), "end": p.get("END_PRD_DE")} for p in prd],
        "objs": sorted(objs.values(), key=lambda o: int(o["sn"] or 0)),
        "items": items,
    }


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    lst = []
    for line in open(RAW / "list_MT_ZTITLE.jsonl", encoding="utf-8"):
        lst.append(json.loads(line))
    done = set()
    if OUT.exists():
        for line in open(OUT, encoding="utf-8"):
            done.add(json.loads(line)["tbl_id"])
    k = Kosis()
    todo = [t for t in lst if t["TBL_ID"] not in done]
    if limit:
        todo = todo[:limit]
    t0 = time.time()
    ok = fail = 0
    with open(OUT, "a", encoding="utf-8") as fo, open(ERR, "a", encoding="utf-8") as fe:
        for i, t in enumerate(todo, 1):
            org, tbl = t["ORG_ID"], t["TBL_ID"]
            try:
                tb = k.meta(org, tbl, "TBL")
                prd = k.meta(org, tbl, "PRD")
                itm = k.meta(org, tbl, "ITM")
                fo.write(json.dumps(compact(org, tbl, tb, prd, itm), ensure_ascii=False) + "\n")
                fo.flush()
                ok += 1
            except Exception as e:
                fail += 1
                err = e.err if isinstance(e, KosisError) else type(e).__name__
                fe.write(json.dumps({"org_id": org, "tbl_id": tbl, "error": err, "msg": mask(e)}, ensure_ascii=False) + "\n")
                fe.flush()
            if i % 25 == 0:
                print(f"{i}/{len(todo)} ok={ok} fail={fail} elapsed={time.time()-t0:.0f}s", flush=True)
    print(f"DONE ok={ok} fail={fail} elapsed={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
