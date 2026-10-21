"""Step 4: merge list + meta -> data/processed/meta_tables.jsonl (one row per table).

Usage: .venv/Scripts/python.exe -m src.meta.clean
"""
import json
import math
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "meta_tables.jsonl"
SURVEY_BY_STAT = {"1962001": "인구총조사", "2013018": "인구총조사(세종시 2013)", "1962005": "인구총조사(시계열 연계)"}
SE_ORDER = ["년", "반기", "분기", "월", "일", "부정기"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("ㆍ", "·").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def read_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def main():
    z = read_jsonl(RAW / "list_MT_ZTITLE.jsonl")
    otbl = {t["TBL_ID"] for t in read_jsonl(RAW / "list_MT_OTITLE.jsonl")}
    metas = {m["tbl_id"]: m for m in read_jsonl(RAW / "meta_compact.jsonl")}
    rows = []
    for t in z:
        tid = t["TBL_ID"]
        parts = t["PATH"].split("/")
        m = metas.get(tid)
        r = {
            "org_id": t["ORG_ID"], "tbl_id": tid, "tbl_nm": t["TBL_NM"], "stat_id": t["STAT_ID"],
            "survey": SURVEY_BY_STAT.get(t["STAT_ID"], t["STAT_ID"]),
            "in_1876": t["STAT_ID"] == "1962001", "in_otitle_view": tid in otbl,
            "path": t["PATH"], "path_parts": parts, "path_depth": len(parts),
            "section": parts[2] if len(parts) > 2 else None,
            "name_group": parts[3] if len(parts) > 3 else None,
            "send_de": t["SEND_DE"], "rec_tbl_se": t["REC_TBL_SE"], "meta_ok": m is not None,
        }
        if m:
            prd = m["prd"]
            r["prd"] = prd
            ses = [p["se"] for p in prd if p["se"]]
            r["prd_se_list"] = ses
            r["prd_se_main"] = ses[0] if ses else None
            r["start_prd"] = min((p["start"] for p in prd if p["start"]), default=None)
            r["end_prd"] = max((p["end"] for p in prd if p["end"]), default=None)
            objs = m["objs"]
            r["n_obj"] = len(objs)
            r["obj_names"] = [o["nm"] for o in objs]
            r["obj_sizes"] = [o["n"] for o in objs]
            r["items"] = m["items"]
            r["n_items"] = len(m["items"])
            r["units"] = sorted({i["unit"] for i in m["items"] if i.get("unit")})
            r["est_cells_per_period"] = int(math.prod(r["obj_sizes"]) * max(r["n_items"], 1))
            r["tbl_nm_eng"] = m["tbl_nm_eng"]
            r["tbl_nm_meta"] = m["tbl_nm"]
            r["search_text"] = norm(" ".join(
                ["인구총조사", t["TBL_NM"], " ".join(parts[2:]), " ".join(r["obj_names"]),
                 " ".join(i["nm"] for i in m["items"][:50])]))
        rows.append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("rows", len(rows), "meta_ok", sum(r["meta_ok"] for r in rows), "bytes", OUT.stat().st_size)


if __name__ == "__main__":
    main()
