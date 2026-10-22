"""load_meta(): TableCatalog(2.1) JOIN TableMeta(2.2) + 파생 필드 -> list[MetaRecord] (dict).

실행(자체 검사): python -m src.meta.load
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

PRD_SE_CODE = {"년": "Y", "5년": "F", "2년": "F", "월": "M", "분기": "Q", "반기": "H", "부정기": "IR", "IR": "IR"}


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s).split())


def _folders(path: str) -> list[str]:
    # "주제별통계 > 인구 > 조사 > 부문 > 폴더... > 표명" -> 마지막(표명)을 뺀 폴더 목록
    return path.split(" > ")[:-1]


def load_meta(proc_dir: Path = PROC) -> list[dict]:
    meta = {}
    for line in open(proc_dir / "table_meta.jsonl", encoding="utf-8"):
        m = json.loads(line)
        meta[(m["org_id"], m["tbl_id"])] = m
    out = []
    for line in open(proc_dir / "population_table_catalog.jsonl", encoding="utf-8"):
        c = json.loads(line)
        key = (c["org_id"], c["tbl_id"])
        m = meta.get(key) or {"meta_ok": False, "error": "NOT_ENRICHED", "n_obj": 0, "obj_names": [], "obj_sizes": [],
                              "items": [], "n_items": 0, "units": [], "est_cells_per_period": 0, "send_de": None}
        rec = {**c, **{k: v for k, v in m.items() if k not in ("org_id", "tbl_id")}}
        rec["prd_se_codes"] = list(dict.fromkeys(
            PRD_SE_CODE.get(p["frequency_label"], p["frequency_label"]) for p in c["catalog_periods"]))
        folders = _folders(c["paths"][0]["path"])
        rec["section"] = folders[3] if len(folders) > 3 else ""
        rec["name_group"] = folders[4] if len(folders) > 4 else ""
        parts = [c["table_name"], c["survey_name"], *[p["path"] for p in c["paths"]],
                 *rec["obj_names"], *[i["nm"] for i in rec["items"]]]
        rec["search_text"] = _norm(" ".join(parts))
        out.append(rec)
    return out


if __name__ == "__main__":
    recs = load_meta()
    keys = [(r["org_id"], r["tbl_id"]) for r in recs]
    assert len(recs) == 2364, len(recs)
    assert len(set(keys)) == len(keys), "기본키 중복"
    ok = sum(r["meta_ok"] for r in recs)
    print(f"records={len(recs)} unique_keys={len(set(keys))} meta_ok={ok} meta_fail={len(recs)-ok}")
    print("prd_se_codes:", {tuple(sorted(set(r['prd_se_codes']))) for r in recs})
    print("empty section:", sum(not r["section"] for r in recs), "empty name_group:", sum(not r["name_group"] for r in recs))
