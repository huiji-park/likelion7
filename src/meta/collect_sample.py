"""Step 3: numeric sample via statisticsParameterData.do for ~30 stratified tables.

Selection (deterministic; see select_sample): from data/processed/meta_tables.jsonl, stratify by
(period type x number of classification objects x path section x name keyword group), taking the
cheapest table (fewest cells = product of classification sizes x items) in each stratum, plus forced
coverage of every period type and every classification-count 0..max.
Fetch: latest N periods (newEstPrdCnt=NEWEST), all items, all classification values ('ALL');
on err 31 (cell limit) fall back to restricting objL1 to the first top-level codes.
Output: data/raw/sample/{tbl_id}.json (raw rows) and data/raw/sample_index.jsonl (status per table).
Usage: .venv/Scripts/python.exe -m src.meta.collect_sample [--n 30]
"""
import json
import sys
from pathlib import Path

import pandas as pd

from src.kosis.client import Kosis, KosisError, mask

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
SAMPLE_DIR = RAW / "sample"
PRDSE = {"년": "Y", "월": "M", "분기": "Q", "반기": "H", "일": "D", "부정기": "IR", "5년": "F"}  # "5년"->F verified on DT_1GA5502
NEWEST = 2


def select_sample(n=30) -> pd.DataFrame:
    """Deterministic stratified pick (no randomness):
    - forced coverage: every period type, every classification count, every path section (middle-cost table of each)
    - 3 'large' tables (est cells > 200k) to exercise the cell-limit fallback
    - fill up to n by walking name_group x section strata sorted by tbl_id, taking the middle-cost small table
    """
    df = pd.read_json(ROOT / "data" / "processed" / "meta_tables.jsonl", lines=True, dtype={"tbl_id": str})
    df = df[df["meta_ok"]].copy()
    df["stratum"] = df["prd_se_main"].astype(str) + "|obj" + df["n_obj"].astype(str) + "|" + df["section"].astype(str)
    small = df[df.est_cells_per_period <= 30000].sort_values(["est_cells_per_period", "tbl_id"])
    out = []

    def mid(g):
        return g.iloc[len(g) // 2]["tbl_id"]

    for col in ("prd_se_main", "n_obj", "section"):
        for _, g in small.groupby(col):
            out.append(mid(g))
    big = df[df.est_cells_per_period > 200000].sort_values(["est_cells_per_period", "tbl_id"])
    out += list(big.iloc[[0, len(big) // 2, len(big) - 1]]["tbl_id"])
    groups = sorted(small.groupby("name_group"), key=lambda kv: kv[0])
    i = 0
    while len(set(out)) < n and i < 10 * len(groups):
        out.append(mid(groups[i % len(groups)][1].iloc[i // len(groups):]) if len(groups[i % len(groups)][1].iloc[i // len(groups):]) else groups[0][1].iloc[0]["tbl_id"])
        i += 1
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return df[df.tbl_id.isin(uniq[:n])].sort_values("tbl_id")


def fetch_table(k: Kosis, row):
    se = PRDSE.get(row["prd_se_main"])
    if not se:
        return None, "unknown prdSe"
    meta = row["_meta"]
    base = {"orgId": row["org_id"], "tblId": row["tbl_id"], "itmId": "ALL", "prdSe": se, "newEstPrdCnt": str(NEWEST)}
    objs = meta["objs"]
    attempts = []
    full = {f"objL{o['sn']}": "ALL" for o in objs}
    attempts.append(("ALL", full))
    for topn in (3, 1):
        if objs:
            o1 = objs[0]
            tops = [v[0] for v in o1["values"] if not v[2]][:topn]
            if tops:
                a = dict(full)
                a["objL1"] = "+".join(tops)
                attempts.append((f"objL1 first {topn} top codes", a))
    last = None
    for label, extra in attempts:
        try:
            data = k.data(**base, **extra)
            return {"mode": label, "rows": data}, None
        except KosisError as e:
            last = f"{e.err}: {e.msg}"
            if e.err != "31":
                break
        except Exception as e:
            last = mask(e)
            break
    return None, last


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 30
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    sel = select_sample(n)
    metas = {}
    for line in open(RAW / "meta_compact.jsonl", encoding="utf-8"):
        m = json.loads(line)
        metas[m["tbl_id"]] = m
    k = Kosis()
    with open(RAW / "sample_index.jsonl", "w", encoding="utf-8") as fi:
        for _, r in sel.iterrows():
            row = r.to_dict()
            row["_meta"] = metas[row["tbl_id"]]
            res, err = fetch_table(k, row)
            rec = {"tbl_id": row["tbl_id"], "tbl_nm": row["tbl_nm"], "stratum": row["stratum"], "prd_se": row["prd_se_main"],
                   "n_obj": int(row["n_obj"]), "ok": res is not None, "error": err}
            if res:
                rec["mode"] = res["mode"]
                rec["n_rows"] = len(res["rows"])
                (SAMPLE_DIR / f"{row['tbl_id']}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            fi.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fi.flush()
            print(rec["tbl_id"], rec["ok"], rec.get("n_rows"), err, flush=True)


if __name__ == "__main__":
    main()
