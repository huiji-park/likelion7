"""Step 5: metadata EDA. Reads data/processed/meta_tables.jsonl, writes
  docs/reports/data/figures/*.png
  data/processed/profile_stats.json  (all numbers quoted in the report)
Usage: .venv/Scripts/python.exe -m src.meta.profile
"""
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "docs" / "reports" / "data" / "figures"
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

OBJ_KINDS = [
    ("행정구역", r"행정구역|시도|시군구|읍면동|지역|시군|특별시|광역시"),
    ("성별", r"^성$|(?<!구)(?<!성)성별|남녀"),  # 세대구성별/유형구성별 제외
    ("연령", r"연령|나이|세별|출생연도|출생코호트"),
    ("혼인", r"혼인"),
    ("교육", r"교육|학력|학교|전공|졸업"),
    ("가구(원수·유형·세대)", r"가구|세대|가구원"),
    ("주택·거처", r"주택|거처|건축|방수|점유|주거|주택"),
    ("경제활동·산업·직업", r"산업|직업|종사|경제활동|취업|근로|사업체"),
    ("국적·이주·외국인", r"국적|외국|이주|이민|귀화|출신국"),
    ("종교", r"종교"),
    ("출생·이동·거주", r"이동|출생|거주|통근|통학|전입|전출|입주"),
    ("시점·기타 구분", r"연도|시점|기준|구분"),
]


def kind_of(name: str) -> str:
    for k, pat in OBJ_KINDS:
        if re.search(pat, name):
            return k
    return "기타"


def barh(series, title, fname, xlabel="통계표 수", top=None, figsize=(8, 5)):
    s = series.sort_values(ascending=True)
    if top:
        s = s.tail(top)
    fig, ax = plt.subplots(figsize=figsize)
    ax.barh(s.index.astype(str), s.values, color="#3b6ea5")
    for i, v in enumerate(s.values):
        ax.text(v, i, f" {v}", va="center", fontsize=8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=130)
    plt.close(fig)


def bar(series, title, fname, xlabel="", ylabel="통계표 수", figsize=(8, 4.5)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(series.index.astype(str), series.values, color="#3b6ea5")
    for i, v in enumerate(series.values):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=130)
    plt.close(fig)


GEO_SUFFIX = re.compile(r"\s*[-–]\s*(전국|시도|시군구|읍면동|시군구,? ?읍면동|전국,? ?시도|[^-–]*)$")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_json(ROOT / "data" / "processed" / "meta_tables.jsonl", lines=True, dtype={"tbl_id": str, "stat_id": str, "start_prd": str, "end_prd": str})
    S = {}
    S["n_total"] = len(df)
    S["by_stat_id"] = df.stat_id.value_counts().to_dict()
    S["n_in_1876"] = int(df.in_1876.sum())
    S["n_in_otitle"] = int(df.in_otitle_view.sum())
    S["meta_ok"] = int(df.meta_ok.sum())
    S["meta_fail"] = int((~df.meta_ok).sum())
    S["rec_tbl_se"] = df.rec_tbl_se.value_counts().to_dict()
    S["send_de_range"] = [df.send_de.min(), df.send_de.max()]

    # ---- path structure ----
    S["section_counts"] = df.section.value_counts().to_dict()
    S["name_group_counts"] = df.name_group.value_counts(dropna=False).to_dict()
    S["path_depth_counts"] = df.path_depth.value_counts().sort_index().to_dict()
    S["n_distinct_paths"] = int(df.path.nunique())
    pc = df.path.value_counts()
    S["tables_per_path_describe"] = pc.describe().round(2).to_dict()
    S["top_paths"] = pc.head(15).to_dict()
    g = df.groupby(["section", "name_group"]).size().sort_values(ascending=False)
    S["section_group_counts"] = {f"{a}/{b}": int(c) for (a, b), c in g.items()}
    gg = pd.Series(g.values, index=[f"{a}/{b}" for (a, b) in g.index])
    barh(gg, "부문/하위분류별 통계표 수 (인구총조사 전체 목록)", "01_tables_by_section_group.png", figsize=(9, 10))
    bar(df.path_depth.value_counts().sort_index(), "경로 깊이(인구/인구총조사 포함 단계 수) 분포", "02_path_depth.png", xlabel="깊이")

    ok = df[df.meta_ok].copy()
    # ---- period ----
    S["prd_se_main"] = ok.prd_se_main.value_counts(dropna=False).to_dict()
    S["prd_se_multi"] = int((ok.prd_se_list.apply(len) > 1).sum())
    S["prd_se_lists"] = ok.prd_se_list.apply(lambda x: "+".join(sorted(x))).value_counts().to_dict()
    ok["start_y"] = ok.start_prd.str[:4].astype(float)
    ok["end_y"] = ok.end_prd.str[:4].astype(float)
    ok["span"] = ok.end_y - ok.start_y + 1
    S["start_year_counts"] = ok.start_y.astype(int).value_counts().sort_index().to_dict()
    S["end_year_counts"] = ok.end_y.astype(int).value_counts().sort_index().to_dict()
    S["span_describe"] = ok.span.describe().round(2).to_dict()
    S["single_period_tables"] = int((ok.start_prd == ok.end_prd).sum())
    S["prd_format_samples"] = {se: ok[ok.prd_se_main == se].start_prd.head(3).tolist() for se in ok.prd_se_main.dropna().unique()}
    bar(ok.prd_se_main.fillna("미상").value_counts(), "수록 주기(PRD_SE) 분포", "03_period_type.png")
    bar(ok.end_y.astype(int).value_counts().sort_index(), "최신 시점(연도) 분포", "04_latest_year.png", xlabel="최신 수록 연도")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(ok.span.dropna(), bins=range(0, int(ok.span.max()) + 3), color="#3b6ea5")
    ax.set_title("수록기간 길이(연) 분포")
    ax.set_xlabel("연")
    ax.set_ylabel("통계표 수")
    fig.tight_layout()
    fig.savefig(FIG / "05_span.png", dpi=130)
    plt.close(fig)

    # ---- classification ----
    S["n_obj_counts"] = ok.n_obj.value_counts().sort_index().to_dict()
    kinds = Counter()
    kinds_names = {}
    for names in ok.obj_names:
        ks = {kind_of(n) for n in names}
        for k in ks:
            kinds[k] += 1
    for names in ok.obj_names:
        for n in names:
            kinds_names.setdefault(kind_of(n), Counter())[n] += 1
    S["obj_kind_table_counts"] = dict(kinds.most_common())
    S["obj_kind_top_names"] = {k: dict(c.most_common(6)) for k, c in kinds_names.items()}
    S["obj_name_top"] = dict(Counter(n for ns in ok.obj_names for n in ns).most_common(30))
    S["n_distinct_obj_names"] = len({n for ns in ok.obj_names for n in ns})
    S["first_obj_kind"] = ok.obj_names.apply(lambda x: kind_of(x[0]) if x else "(없음)").value_counts().to_dict()
    S["items_describe"] = ok.n_items.describe().round(2).to_dict()
    S["items_counts_top"] = ok.n_items.value_counts().sort_index().head(15).to_dict()
    S["obj_size_max"] = int(max((max(s) for s in ok.obj_sizes if s), default=0))
    S["est_cells_describe"] = ok.est_cells_per_period.describe().round(0).to_dict()
    S["est_cells_gt_40000"] = int((ok.est_cells_per_period > 40000).sum())
    S["units_counts"] = Counter(u for us in ok.units for u in us).most_common(40)
    S["n_distinct_units"] = len({u for us in ok.units for u in us})
    S["tables_multi_unit"] = int((ok.units.apply(len) > 1).sum())
    S["tables_no_unit"] = int((ok.units.apply(len) == 0).sum())
    S["item_name_top"] = Counter(i["nm"] for its in ok["items"] for i in its).most_common(25)
    bar(pd.Series(kinds).sort_values(ascending=False), "분류 종류별 통계표 수(분류명 키워드 규칙)", "06_obj_kinds.png", ylabel="통계표 수")
    bar(ok.n_obj.value_counts().sort_index(), "분류(objL) 개수 분포", "07_n_obj.png", xlabel="분류 수")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(ok.n_items.clip(upper=60), bins=range(0, 62), color="#3b6ea5")
    ax.set_title("항목 수 분포 (60 초과는 60으로 표시)")
    ax.set_xlabel("항목 수")
    ax.set_ylabel("통계표 수")
    fig.tight_layout()
    fig.savefig(FIG / "08_n_items.png", dpi=130)
    plt.close(fig)
    us = pd.Series(dict(S["units_counts"])).head(15)
    barh(us, "단위(UNIT_NM) 상위 15 (항목 단위 기준 통계표 수)", "09_units.png", figsize=(8, 5))

    # ---- names ----
    df["nm_norm"] = df.tbl_nm.str.replace(r"\s+", "", regex=True)
    S["tbl_nm_exact_dup_names"] = int(df.tbl_nm.duplicated(keep=False).sum())
    S["tbl_nm_distinct"] = int(df.tbl_nm.nunique())
    dup = df[df.tbl_nm.duplicated(keep=False)].groupby("tbl_nm").size().sort_values(ascending=False)
    S["tbl_nm_dup_groups"] = int(len(dup))
    S["tbl_nm_dup_top"] = dup.head(15).to_dict()
    S["tbl_nm_dup_same_path"] = int(df[df.tbl_nm.duplicated(keep=False)].groupby(["tbl_nm", "path"]).size().gt(1).sum())
    df["stem"] = df.tbl_nm.str.replace(GEO_SUFFIX, "", regex=True).str.replace(r"\s+", "", regex=True)
    stem = df.groupby("stem").tbl_id.nunique()
    S["stem_distinct"] = int(len(stem))
    S["stem_groups_ge2"] = int((stem >= 2).sum())
    S["stem_top"] = stem.sort_values(ascending=False).head(15).to_dict()
    S["name_len_describe"] = df.tbl_nm.str.len().describe().round(1).to_dict()
    S["name_has_dash_geo"] = int(df.tbl_nm.str.contains(r"\s[-–]\s").sum())
    geo = df.tbl_nm.str.extract(r"[-–]\s*([^-–]+)$")[0].str.strip()
    S["name_geo_suffix_top"] = geo.value_counts().head(15).to_dict()
    S["name_has_year_range"] = int(df.tbl_nm.str.contains(r"\d{4}\s*[~-]\s*\d{4}|\(\d{4}").sum())
    S["name_kw"] = {k: int(df.tbl_nm.str.contains(k).sum()) for k in ["성별", "연령", "성 및 연령", "가구", "주택", "시도", "시군구", "읍면동", "전국", "2010", "2015", "2020", "추이", "비율", "지수", "10%", "표본", "전수"]}
    S["prefix_2015_before_after"] = {"2015년 이후": int(df.path.str.contains("2015년 이후").sum()), "2015년 이전 표기 경로": int(df.path.str.contains("2015년 이전|2010").sum())}

    # same name+same structure -> near-identical
    sig = ok.assign(sig=ok.tbl_nm.str.replace(r"\s+", "", regex=True) + "|" + ok.obj_names.apply("|".join) + "|" + ok.n_items.astype(str))
    S["same_name_and_structure_groups"] = int((sig.groupby("sig").tbl_id.nunique() >= 2).sum())

    S["tables_with_meta_but_no_prd"] = int(ok.prd_se_main.isna().sum())
    (ROOT / "data" / "processed" / "profile_stats.json").write_text(json.dumps(S, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("profile done; figures:", sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
