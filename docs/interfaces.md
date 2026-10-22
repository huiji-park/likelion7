# 모듈 인터페이스 계약 (v0.1)

> project-lead만 수정한다. 바꿔야 할 필드·시그니처가 있으면 보고서에 제안을 적고 리드에게 요청한다.
> 작성: 2026-10-22 · 기준: `data/census-eda` 브랜치의 정제본 `data/processed/meta_tables.jsonl` 필드명을 그대로 표준으로 채택했다.

## 0. 공통 원칙
- 모든 수치는 `DataRow`(3절)에서 출발한다. 분석·요약·차트는 `DataRow`의 키(`row_key`)로 원본을 가리키며, 새 숫자를 만들지 않는다.
- 수치 계산은 `src/analysis/`의 코드가 한다. LLM 입력에는 `AnalysisResult`의 결과값만 넣고, LLM 출력의 숫자는 이 값과 대조한다(7절).
- 출처는 최소 `(survey, tbl_nm, tbl_id, org_id)` 네 가지를 항상 함께 들고 다닌다 → `Source` 객체.
- 문자열은 UTF-8, JSON 파일은 `ensure_ascii=False`. 시점은 KOSIS 표기 그대로 문자열(`"2020"`, `"202403"`, `"2024Q1"` 아님 → 아래 표기 규칙).
- API 키는 `src/kosis/client.get_key()`로만 읽는다. 어떤 객체·로그·캐시 키에도 넣지 않는다.
- 코드는 dataclass 또는 TypedDict로 구현하고 JSON 직렬화가 가능해야 한다. 필드 추가는 허용(하위 호환), 이름 변경·삭제는 리드 승인.

## 1. 디렉터리와 담당
| 경로 | 내용 | 담당 |
|---|---|---|
| `src/kosis/client.py` | KOSIS 호출(캐시·재시도·마스킹) — **존재** | data |
| `src/kosis/fetch.py` | `DataRequest` → `DataResult` 변환(표준화, 40,000셀 분할) | data |
| `src/meta/` | 목록·메타 수집, 정제(`MetaRecord` 생성) — **존재** | data |
| `src/pipeline/query.py` | 질문 → `ParsedQuery` | ai |
| `src/search/` | `ParsedQuery` → `TableCandidate[]` | ai |
| `src/analysis/` | `DataResult` → `AnalysisResult[]` | ai |
| `src/llm/` | HCX 호출, 요약 생성 → `Answer` | ai |
| `src/pipeline/session.py` | `ConversationState` 관리, 턴 처리 진입점 | ai |
| `src/chart/` | `ChartSpec` + `DataResult` → 이미지/Plotly figure | service |
| `app/` | UI, 백엔드 API | service |
| `eval/` | 골든셋, 평가 코드 | eval |
| `data/processed/` | 커밋되는 정제본 / `data/raw`, `data/cache`, `data/logs`는 커밋 금지 | data |

## 2. MetaRecord — 정제 메타데이터 (`data/processed/meta_tables.jsonl`, 1줄 1표)
| 필드 | 타입 | 설명 |
|---|---|---|
| `org_id` | str | 기관 ID (인구총조사 `"101"`) |
| `tbl_id` | str | 통계표 ID. **(org_id, tbl_id)가 기본키** |
| `tbl_nm` | str | 통계표명 원문 |
| `tbl_nm_eng` | str \| null | 영문 표명 |
| `stat_id` | str | 조사 ID (목록 `STAT_ID`) |
| `survey` | str | 조사명 (14개 조사 중 하나, 예: `"인구총조사"`) |
| `path`, `path_parts`, `path_depth` | str, list[str], int | KOSIS 주제 경로 |
| `section`, `name_group` | str | 경로 3·4번째 단계(부문, 조사연도 폴더). **조사 연도는 표명이 아니라 여기에 있다** |
| `send_de` | str | 최종 갱신일 `YYYY-MM-DD` |
| `prd` | list[{se, start, end}] | 주기별 수록기간 |
| `prd_se_main` | str | 대표 주기(한글: `5년`/`년`/`부정기`/`월`/`분기`/`반기`) |
| `start_prd`, `end_prd` | str | 수록 시작·끝 시점 |
| `n_obj`, `obj_names`, `obj_sizes` | int, list[str], list[int] | 분류(objL1..) 이름·값 개수 (순서 = objL 번호) |
| `items` | list[{id, nm, unit, unit_id}] | 항목. 단위는 **항목별**이며 빈 문자열 가능 |
| `n_items`, `units` | int, list[str] | |
| `est_cells_per_period` | int | 시점 1개당 추정 셀 수(상한). 40,000 초과면 분류값 지정 필수 |
| `search_text` | str | 검색용 정규화 텍스트(NFKC, 표명+경로+분류명+항목명) |
| `meta_ok` | bool | 메타 수집 성공 여부 |
| 조사별 확장 필드 | — | 예: 인구총조사 `in_1876`, `in_otitle_view`. 공통 로직에서 의존하지 않는다 |

분류값 목록(코드·이름·`UP_ITM_ID`)은 용량 때문에 별도 파일로 둔다: `data/processed/obj_values/<org_id>_<tbl_id>.json` (형식 `{ "objL1": [{"code","nm","up"}...], ... }`). 지금은 `data/raw/meta_compact.jsonl`에만 있으므로 data-engineer가 생성기를 추가한다(작업 D-2).

## 3. 수치 조회
### 3.1 DataRequest
```python
DataRequest(
    org_id: str, tbl_id: str,
    prd_se: str,                 # 요청 코드: Y(년) F(5년·다년) IR(부정기) H(반기) Q(분기) M(월)
    start_prd: str | None = None, end_prd: str | None = None,
    recent_n: int | None = None, # newEstPrdCnt. start/end와 동시에 쓰지 않는다
    itm_ids: list[str] = ["ALL"],
    obj_filters: dict[str, list[str]] = {},  # {"objL1": ["00","11"], ...}; 미지정 분류는 "ALL"
)
```
- 메타 한글 주기 → 요청 코드: `5년→F`, `년→Y`, `부정기→IR`, `월→M`, `분기→Q`, `반기→H`. 5년 주기 표에 `Y`를 보내면 err 30이 난다(EDA 4.7).
- `est_cells_per_period × 시점 수 > 40,000`이면 `fetch.py`가 분류값을 쪼개 여러 번 호출하고 합친다. 쪼개도 불가하면 `KosisError("31")`을 올리고 `DataResult.warnings`에 남긴다.

### 3.2 DataRow (표준 수치 1행)
| 필드 | 타입 | 설명 |
|---|---|---|
| `row_key` | str | `f"{tbl_id}|{prd_de}|{itm_id}|{c1}|{c2}|..."` (빈 분류 생략). 분석·요약이 원본을 가리키는 키 |
| `org_id`, `tbl_id`, `tbl_nm` | str | |
| `prd_de` | str | 시점: 년 `YYYY`, 월 `YYYYMM`, 분기 `YYYYQ`(KOSIS 원문 그대로) |
| `prd_se_req`, `prd_se_resp` | str | 요청 코드와 응답 `PRD_SE`(5년 주기는 `A`로 돌아옴) — 둘 다 보관 |
| `itm_id`, `itm_nm` | str | 항목 |
| `dims` | list[{obj_nm, code, nm}] | C1..C8 순서대로 분류명·코드·값명 |
| `unit` | str | 행 단위(`UNIT_NM`). 비어 있으면 메타 `items[].unit`으로 보충하고, 그래도 없으면 `""` |
| `raw` | str | 응답 `DT` 원문 |
| `value` | float \| None | 숫자로 변환된 값. 숫자가 아니면 None |
| `status` | str | `ok` / `dash`(`-`) / `symbol`(그 밖의 기호) / `empty` |
| `lst_chn_de` | str \| None | 최종 변경일 |

`-`와 `0`은 반드시 구분한다(`-`는 `value=None, status="dash"`). 의미가 확인되기 전까지 응답문에서는 "자료 없음(-)"으로 표기한다.

### 3.3 DataResult
```python
DataResult(request: DataRequest, rows: list[DataRow], source: Source,
           fetched_at: str,          # ISO8601
           from_cache: bool, partial: bool, warnings: list[str])
Source(survey: str, tbl_nm: str, tbl_id: str, org_id: str,
       url: str)                     # KOSIS 통계표 화면 URL(키 없음):
                                     # https://kosis.kr/statHtml/statHtml.do?orgId={org_id}&tblId={tbl_id}
```
함수: `src/kosis/fetch.py :: fetch_data(req: DataRequest, use_cache: bool = True) -> DataResult`

## 4. 질의 분석과 검색
### 4.1 ParsedQuery
```python
ParsedQuery(
    text: str,                       # 원 질문
    intent: str,                     # value | trend | compare | share | rank | table_guide | chart | followup | unanswerable
    topic_keywords: list[str],
    period: {"start": str|None, "end": str|None, "recent_n": int|None, "latest": bool},
    region: {"level": "전국|시도|시군구|읍면동|None", "names": list[str]},
    filters: dict[str, list[str]],   # {"성별": ["여자"], "연령별": ["65세이상"]} — 분류명 키워드 기준
    operation: str | None,           # 6절 op 이름
    chart_type: str | None,          # 8절 type
    refers_previous: bool,           # "그거", "이걸" 등 이전 턴 참조
)
```
함수: `src/pipeline/query.py :: parse_query(text: str, state: ConversationState | None) -> ParsedQuery`

### 4.2 TableCandidate
```python
TableCandidate(org_id, tbl_id, tbl_nm, survey, path, name_group,
               period: str,          # "2015~2025 (년)"
               score: float, rank: int,
               reasons: list[str],   # 매칭 근거(키워드·분류·기간)
               region_level: str | None)
```
함수: `src/search/__init__.py :: search_tables(q: ParsedQuery, k: int = 5) -> list[TableCandidate]`
- 같은 표명이 연도 폴더·지역 단계별로 반복되므로(EDA 4.6), 후보 제시는 `name_group`·`region_level`로 구분해 보여준다.

## 5. 조회 조건 결정
함수: `src/pipeline/resolve.py :: build_request(q: ParsedQuery, table: MetaRecord) -> DataRequest | Unanswerable`
- 기간이 수록기간 밖이거나, 질문의 분류가 표에 없으면 `Unanswerable`(9절)을 돌려준다.

## 6. AnalysisResult — 수치 분석
```python
AnalysisResult(
    op: str,                  # value | diff | pct_change | cagr | mean | share | max | min | rank
    formula: str,             # 사람이 읽는 식. 예: "(B - A) / A × 100"
    inputs: list[{"row_key": str, "label": str, "value": float, "unit": str, "prd_de": str}],
    result: float | list[...],# rank는 [{"label","value"}...]
    unit: str,                # 결과 단위. pct_change → "%", diff → 입력 단위, share → "%"
    decimals: int,            # 표시 자릿수 (기본: % 1자리, 정수 단위 0자리)
    period: str,              # "2015→2020"
    source: Source,
    notes: list[str],         # 비교 한계(단위 혼재, 분류 기준 변경, '-' 제외 등)
)
```
함수: `src/analysis/stats.py :: analyze(result: DataResult, q: ParsedQuery) -> list[AnalysisResult]`
- 입력에 `status != "ok"`인 행이 끼면 계산하지 않고 `notes`에 남긴다. 단위가 다른 값끼리는 계산하지 않는다.

## 7. Answer — 최종 응답
```python
Answer(
    answerable: bool,
    text: str,                        # 사용자에게 보일 응답(요약)
    numbers: list[AnalysisResult],    # text에 등장하는 모든 수치의 근거
    sources: list[Source],
    candidates: list[TableCandidate], # 통계표 안내형 응답일 때
    chart: ChartSpec | None,
    unanswerable: Unanswerable | None,
    checks: {"numbers_match": bool, "unmatched": list[str]},  # text의 숫자 ↔ numbers 대조 결과
)
```
함수: `src/llm/summarize.py :: summarize(q, analyses, table, state) -> Answer`
- `text` 안의 모든 숫자는 `numbers`(또는 `DataRow.value`)에서 온 것이어야 한다. 대조 실패 시 LLM 문장 대신 템플릿 문장으로 대체한다.
- 응답 끝에 출처 줄: `출처: {survey} 「{tbl_nm}」({tbl_id}), KOSIS`.

## 8. ChartSpec
```python
ChartSpec(
    type: str,                 # line | bar | pie | stacked_bar | scatter
    title: str,
    x: {"field": "prd_de" | "dim:<obj_nm>" | "itm_nm", "label": str},
    y: {"field": "value", "label": str, "unit": str},
    series: {"field": "dim:<obj_nm>" | "itm_nm" | None},
    row_keys: list[str],       # 그릴 DataRow 목록(데이터는 DataResult에서 꺼낸다)
    source: Source,
    options: dict,             # 정렬, 상위 N, 로그축 등 선택 옵션
)
```
함수: `src/chart/render.py :: render_chart(spec: ChartSpec, data: DataResult) -> plotly.graph_objects.Figure`
- 기본 유형: 시계열 → line, 항목·지역 비교 → bar, 구성비 → pie(항목 ≤ 6) 또는 stacked_bar, 두 지표 관계 → scatter.
- 차트 제목·축에 단위와 기간을 넣고, 하단에 출처를 표기한다.

## 9. Unanswerable
```python
Unanswerable(code: str, reason: str, suggestion: str)
```
| code | 상황 |
|---|---|
| `NO_TABLE` | 범위(14개 조사) 안에 맞는 통계표가 없음 |
| `OUT_OF_PERIOD` | 요청 기간이 수록기간 밖 |
| `NO_DIMENSION` | 요청 분류(지역·성·연령 등)가 표에 없음 |
| `NO_VALUE` | 값이 `-`/비숫자 |
| `NOT_COMPARABLE` | 단위·분류 기준이 달라 비교 불가 |
| `OUT_OF_SCOPE` | 통계 질의가 아님, 예측·인과·정책 평가 요구 |
| `API_ERROR` | KOSIS 호출 실패(셀 제한 포함) |

## 10. ConversationState — 연속 대화
```python
ConversationState(
    session_id: str,
    turn: int,
    table: TableCandidate | None,     # 현재 선정 통계표
    candidates: list[TableCandidate], # 직전 제시 후보("두 번째 표로")
    request: DataRequest | None,      # 현재 조회 조건
    result_ref: str | None,           # DataResult 캐시 키 (본문은 저장하지 않음)
    analyses: list[AnalysisResult],   # 직전 분석
    chart: ChartSpec | None,          # 직전 차트
    history: list[{"turn": int, "user": str, "intent": str, "answer_text": str, "sources": list[Source]}],
)
```
함수: `src/pipeline/session.py :: handle_turn(text: str, state: ConversationState) -> tuple[Answer, ConversationState]`
- 상태 갱신 규칙: "최근 5년으로" → `request` 기간만 교체, "막대로" → `chart.type`만 교체, "다른 지역/항목" → `request.obj_filters` 교체, 새 주제 → `table` 이하 초기화. 이전 턴의 `history`는 유지.

## 11. 변경 절차
1. 필요한 변경을 보고서 "다른 역할에 대한 요청"에 적고 리드에게 전달.
2. 리드가 이 문서 버전을 올리고(`v0.x`) 아래 이력에 남긴 뒤 `lead/` 브랜치로 푸시.

| 버전 | 날짜 | 변경 |
|---|---|---|
| v0.1 | 2026-10-22 | 최초 작성. MetaRecord는 census-eda 정제본 필드 채택 |
