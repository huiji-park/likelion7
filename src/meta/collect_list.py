"""Step 1: recursively crawl statisticsList.do for 인구총조사 tables.

Start points (all verified by API responses):
  MT_ZTITLE (국내통계 주제별) parentListId=A_4          -> 인구 > 인구총조사
  MT_OTITLE (국내통계 기관별) parentListId=MT_CTITLE_A  -> 국가데이터처(101) > 인구총조사
Output: data/raw/list_{view}.jsonl (one row per table leaf, with PATH) and
        data/raw/list_nodes_{view}.jsonl (folder nodes).
Usage: .venv/Scripts/python.exe -m src.meta.collect_list
"""
import json
import sys
from pathlib import Path

from src.kosis.client import Kosis

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
STARTS = {
    "MT_ZTITLE": ("A_4", "인구/인구총조사"),
    "MT_OTITLE": ("MT_CTITLE_A", "국가데이터처/인구총조사"),
}


def crawl(k: Kosis, vw: str, start: str, prefix: str):
    tables, nodes, seen = [], [], set()

    def rec(pid, path, depth):
        if pid in seen:
            return
        seen.add(pid)
        rows = k.list(vw, pid)
        for r in rows:
            if r.get("TBL_ID"):
                tables.append({**r, "PATH": path, "DEPTH": depth, "PARENT_LIST_ID": pid})
            else:
                nodes.append({**r, "PATH": path, "DEPTH": depth, "PARENT_LIST_ID": pid})
                rec(r["LIST_ID"], f"{path}/{r['LIST_NM']}", depth + 1)

    rec(start, prefix, 1)
    return tables, nodes


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    k = Kosis()
    for vw, (start, prefix) in STARTS.items():
        tables, nodes = crawl(k, vw, start, prefix)
        for name, rows in (("list", tables), ("list_nodes", nodes)):
            with open(RAW / f"{name}_{vw}.jsonl", "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(vw, "start", start, "tables", len(tables), "unique TBL_ID", len({(t['ORG_ID'], t['TBL_ID']) for t in tables}),
              "nodes", len(nodes), file=sys.stderr)


if __name__ == "__main__":
    main()
