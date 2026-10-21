"""Step 5b: profile numeric sample (data/raw/sample/*.json) -> data/processed/sample_stats.json + figure.
Usage: .venv/Scripts/python.exe -m src.meta.profile_sample
"""
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
FIG = ROOT / "docs" / "reports" / "data" / "figures"
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
NUM = re.compile(r"^-?\d+(\.\d+)?$")


def main():
    idx = [json.loads(l) for l in open(RAW / "sample_index.jsonl", encoding="utf-8")]
    out = {"tables": [], "failed": [], "cols": Counter(), "tokens": Counter(), "prd_formats": Counter(), "prd_se": Counter(),
           "units": Counter(), "lst_chn_empty": 0, "rows": 0}
    for rec in idx:
        if not rec["ok"]:
            out["failed"].append({"tbl_id": rec["tbl_id"], "error": rec["error"]})
            continue
        res = json.load(open(RAW / "sample" / f"{rec['tbl_id']}.json", encoding="utf-8"))
        rows = res["rows"]
        toks = Counter()
        nums = []
        decimals = 0
        for r in rows:
            dt = r.get("DT")
            if dt is None:
                toks["<missing key>"] += 1
            elif NUM.match(dt.strip()):
                v = float(dt)
                nums.append(v)
                decimals += "." in dt
            else:
                toks[repr(dt)] += 1
            out["cols"].update(r.keys())
            out["prd_formats"][re.sub(r"\d", "9", r.get("PRD_DE", ""))] += 1
            out["prd_se"][r.get("PRD_SE")] += 1
            out["units"][r.get("UNIT_NM") or "(빈값)"] += 1
            out["lst_chn_empty"] += not r.get("LST_CHN_DE")
        out["rows"] += len(rows)
        out["tokens"].update(toks)
        out["tables"].append({
            "tbl_id": rec["tbl_id"], "tbl_nm": rec["tbl_nm"], "prd_se_meta": rec["prd_se"], "n_obj": rec["n_obj"], "mode": rec["mode"],
            "n_rows": len(rows), "n_numeric": len(nums), "n_nonnumeric": sum(toks.values()), "nonnumeric_tokens": dict(toks),
            "n_zero": sum(v == 0 for v in nums), "n_negative": sum(v < 0 for v in nums), "n_decimal": decimals,
            "min": min(nums) if nums else None, "max": max(nums) if nums else None,
            "periods": sorted({r.get("PRD_DE") for r in rows}), "prd_se_resp": sorted({r.get("PRD_SE") for r in rows}),
            "units": sorted({r.get("UNIT_NM") or "(빈값)" for r in rows}),
            "n_items": len({r.get("ITM_ID") for r in rows}),
            "dup_keys": len(rows) - len({tuple(r.get(f"C{i}") for i in range(1, 9)) + (r.get("ITM_ID"), r.get("PRD_DE")) for r in rows}),
        })
    for k in ("cols", "tokens", "prd_formats", "prd_se", "units"):
        out[k] = dict(out[k].most_common())
    out["n_tables_ok"] = len(out["tables"])
    out["n_tables_failed"] = len(out["failed"])
    out["tables_with_nonnumeric"] = sum(1 for t in out["tables"] if t["n_nonnumeric"])
    out["tables_with_zero"] = sum(1 for t in out["tables"] if t["n_zero"])
    out["tables_with_decimal"] = sum(1 for t in out["tables"] if t["n_decimal"])
    out["tables_with_negative"] = sum(1 for t in out["tables"] if t["n_negative"])
    out["tables_with_dup_keys"] = sum(1 for t in out["tables"] if t["dup_keys"])
    (ROOT / "data" / "processed" / "sample_stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # figure: non-numeric share per table
    ts = [t for t in out["tables"] if t["n_rows"]]
    fig, ax = plt.subplots(figsize=(9, 6))
    ys = [t["tbl_id"] for t in ts]
    ax.barh(ys, [100 * t["n_nonnumeric"] / t["n_rows"] for t in ts], color="#c0504d", label="비숫자 DT")
    ax.barh(ys, [100 * t["n_zero"] / t["n_rows"] for t in ts], left=[100 * t["n_nonnumeric"] / t["n_rows"] for t in ts], color="#7f7f7f", label="0 값")
    ax.set_xlabel("행 비율(%)")
    ax.set_title("수치 표본: 표별 비숫자 DT 및 0 값 비율")
    ax.tick_params(axis="y", labelsize=7)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "10_sample_nonnumeric.png", dpi=130)
    plt.close(fig)
    print("ok", out["n_tables_ok"], "failed", out["n_tables_failed"], "rows", out["rows"])


if __name__ == "__main__":
    main()
