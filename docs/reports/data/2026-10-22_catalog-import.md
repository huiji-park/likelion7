# 인구 카탈로그 반입 및 getMeta 보강

- 작성: data-engineer · 날짜: 2026-10-22
- 종류: 정제 / API 점검
- 관련 단계: 공통(실전1·2 기반 메타)

## 1. 목적
사용자 제공 `population_table_catalog.jsonl`(2,364표)을 새 기준 메타로 반입하고, KOSIS getMeta로 분류·항목·단위를 보강해 인터페이스 계약 v0.2 (2.1 TableCatalog, 2.2 TableMeta, 2.3 MetaRecord)를 구현한다. 이전 `meta_tables.jsonl`(1,901표)은 기준으로 쓰지 않는다.

## 2. 데이터·대상
- 원본 `population.xls` (2.4MB) -> `data/source/population.xls` (커밋)
- 카탈로그: 2,364표 / 14개 조사 / 기관 5곳. API 호출 없음.
- 보강: KOSIS OpenAPI `statisticsData.do?method=getMeta&type=ITM` (분류/항목/단위), `statisticsList.do?method=getList&vwCd=MT_ZTITLE&parentListId=<list_id>` (send_de). 조회일 2026-10-22.

## 3. 수행 내용
```bash
# 환경: .venv(3.12), KOSIS_ENV_PATH는 메인 폴더 .env (키 값은 출력·기록하지 않음)
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
python src/meta/preprocess_population.py        # 카탈로그 재생성 (API 미사용)
python -m src.meta.enrich_meta                  # getMeta 보강 (재개 가능, 실패 표만 재시도)
python -m src.meta.load                         # 자체 검사
```
- `src/meta/preprocess_population.py`: 사용자 코드에서 `ROOT`(`parents[2]`), `SOURCE`, `OUTPUT` 3줄만 수정. 로직 변경 없음.
- `src/kosis/client.py`: census-eda 코드에서 사용자 절대경로 `DEFAULT_ENV` 제거. 키 탐색 순서 = 환경변수 `KOSIS_API_KEY` -> `KOSIS_ENV_PATH` 파일 -> 저장소 루트 `.env`. 캐시 경로·캐시 키 계산은 그대로.
- `src/meta/enrich_meta.py`: 표별 ITM 메타 1회 + 폴더 getList(send_de)를 호출. 기존 캐시 재사용으로 1,901표는 호출 없이 처리, 나머지만 신규 호출(전체 274초, 실패 0). 분당 200건 제한은 클라이언트 간격(0.4초) 및 err 40 대기로 준수.
- `src/meta/load.py`: `load_meta()` = 카탈로그 ⨝ table_meta + `prd_se_codes`, `section`, `name_group`, `search_text`(NFKC).
  - section/name_group: 첫 경로의 4·5번째 단계(표명 제외). 경로가 짧은 표는 빈 문자열.
- `requirements.txt`: requests, python-dotenv, xlrd==2.0.2 (최소 3개). census-eda의 pandas/matplotlib/pyarrow는 이번 코드에서 쓰지 않아 뺐다.

## 4. 결과

### 4.1 재현 검증
`src/meta/preprocess_population.py` 출력과 사용자 제공 jsonl을 `cmp`로 비교: **바이트 단위 동일** (2,364줄, 1,952,490 bytes). 처리 요약: 표 행 2,371, 고유 표 2,364, 병합된 중복 행 7, 조사 14, 기관 코드 5.

### 4.2 카탈로그 요약
기관별: 101 국가데이터처 2,117 / 182 재외동포청 87 / 110 행정안전부 84 / 111 법무부 56 / 358 한국보건산업진흥원 20.

조사별(기관):
| 조사 | 표 수 | 기관 |
|---|---|---|
| 인구총조사 | 1,876 | 국가데이터처 |
| 인구동향조사 | 113 | 국가데이터처 |
| 영주귀국사할린동포실태조사 | 87 | 재외동포청 |
| 지방자치단체외국인주민현황 | 84 | 행정안전부 |
| 출입국자및체류외국인통계 | 56 | 법무부 |
| 국내인구이동통계 | 41 | 국가데이터처 |
| 세종시 특별센서스 | 22 | 국가데이터처 |
| 장래인구추계 | 21 | 국가데이터처 |
| 인구동태패널통계 | 21 | 국가데이터처 |
| 고령친화용품제조업실태조사 | 20 | 한국보건산업진흥원 |
| 장래가구추계 | 8 | 국가데이터처 |
| 국제인구이동통계 | 7 | 국가데이터처 |
| 주민등록인구현황 | 5 | 행정안전부 |
| 주택총조사 | 3 | 국가데이터처 |

주기 조합별: 5년 1,805 / 년 412 / 2년 87 / 부정기 23 / IR 6 / 년+분기+월 15 / 년+월 13 / 년+부정기 2 / 월 1. 요청 코드(`prd_se_codes`) 기준: F 1,892 / Y 412 / IR 29 / Y,Q,M 15 / Y,M 13 / Y,IR 2 / M 1.
경로 깊이(구분자 ` > ` 단계 수): 4단계 40 / 5단계 280 / 6단계 337 / 7단계 1,147 / 8단계 560.
다중 경로 7표: 모두 기관 110(지방자치단체외국인주민현황)의 `TX_11025_A020_A`~`A025_A`, `A029_A` (경로 2개씩). (org_id, tbl_id) 기본키 중복은 없음 (tbl_id 단독으로도 중복 없음).

### 4.3 getMeta 보강 결과 (`data/processed/table_meta.jsonl`)
- 성공(meta_ok=true) **2,364 / 실패 0**. 기관 110·111·182·358도 ITM 메타 응답 구조가 101과 동일해 동작 차이 없음.
- send_de: 2,364표 모두 채워짐(null 0).
- 분류 수 n_obj: 1개 176 / 2개 964 / 3개 1,079 / 4개 143 / 5개 2.
- `est_cells_per_period` 40,000 초과 표: 642 (기관 101 633, 111 8, 110 1). 최대 19,297,278. 이 표들은 조회 시 분류값 지정 또는 분할 필요.
- 단위: 표 단위 `units`가 비어 있는 표가 1,470개(항목 단위 빈 문자열 16,202개). 인구총조사 1,184표가 비어 있다. ITM 메타의 UNIT_NM이 비어 있어도 수치 응답(`UNIT_NM`)에는 있을 수 있으나, 응답에서 `UNIT_NM`이 None으로 온 사례도 확인(아래 4.5의 101 `INH_1B8000F_03`, 비율 값). 항목명에 단위가 포함된 경우(예: "총인구(명)")도 있다. 전수 확인은 미수행.
- 용량: `table_meta.jsonl` 2.1MB(커밋), `obj_values/` 2,364파일 33MB (**미커밋**, 아래 6절).

### 4.4 이전 1,901표와의 대응
census-eda `meta_tables.jsonl` 1,901표는 전부 새 카탈로그에 존재(미존재 0). 조사별: 인구총조사 1,876 / 세종시 특별센서스 22 / 주택총조사 3. 카탈로그 인구총조사 1,876표 중 이전 목록에 없는 표는 0. 즉 이전 1,901표 = 인구총조사 1,876 + 25(세종시 22, 주택총조사 3)이며, 새로 늘어난 463표는 나머지 11개 조사 전부(`인구동향조사` 113, `영주귀국사할린동포실태조사` 87, `지방자치단체외국인주민현황` 84, `출입국자및체류외국인통계` 56, `국내인구이동통계` 41, `장래인구추계` 21, `인구동태패널통계` 21, `고령친화용품제조업실태조사` 20, `장래가구추계` 8, `국제인구이동통계` 7, `주민등록인구현황` 5).

### 4.5 수치 조회 prdSe 확인 (실제 호출)
| 대상 | 요청 prdSe | 결과 |
|---|---|---|
| 2년 주기 182 `DT_182001_A046_2025` (수록 2025~2025) | `F` | 성공 123행, 응답 `PRD_SE=A`, `PRD_DE=2025` |
| 위와 동일 | `Y` / `H` / `IR` | err 30 (데이터가 존재하지 않습니다) |
| 5년 주기 101 `DT_1PA2012` | `Y` | err 30 |
| 년 주기 101 `INH_1B8000F_03`, 110 `TX_11025_A000A`, 111 `DT_1B040A29`, 358 `DT_358005_001` | `Y` | 모두 성공, 응답 `PRD_SE=A` |
| 182 `DT_182001_A046_2025` | `F` | 성공 |

결론: **2년 -> F 확정**(단 2년 주기 표는 영주귀국사할린동포실태조사 87표뿐이며 이 중 1표로만 확인, 수록기간이 1시점이라 2년 간격 자체는 미확인). 요청 코드와 상관없이 연 단위 응답의 `PRD_SE`는 `A`로 돌아오므로 `DataRow.prd_se_resp`는 `A`가 정상(계약서의 "5년 주기만 A" 표현은 "연 단위는 모두 A"로 정정 필요). `DT` 값은 문자열이고 `UNIT_NM`은 None일 수 있다.

## 5. 한계·미확인 사항
- ITM 메타만 전수 보강했다. 분류별 level(계층 깊이)·`TBL` 메타의 영문명 등은 table_meta에 넣지 않음.
- `est_cells_per_period`는 (분류값 수 곱) x (항목 수)의 상한이며 실제 존재하는 셀 수와 다를 수 있다.
- PRD 메타(실제 수록기간)는 카탈로그 `catalog_periods`와 대조하지 않았다 (미확인).
- 단위 공백 표가 많아(4.3) 단위는 수치 응답의 `UNIT_NM`을 우선해야 한다. 전수 점검 미수행.
- 수치 값 자체의 결측 표기(`-`, `x` 등) 점검은 이번 범위 밖(이전 sample EDA는 census-eda 기준).
- 기관별 호출은 각 1표씩만 확인했다. 기관 간 차이를 일반화하지 말 것.

## 6. 다른 역할에 대한 요청 / 다음 단계
- 리드: `obj_values/`(33MB, 2,364파일)는 커밋하지 않았다. 필요하면 `python -m src.meta.enrich_meta` 후 재생성(캐시 있으면 수 분). 저장소에 둘지 별도 배포할지 결정 요청. 두려면 `data/processed/obj_values/`를 .gitignore에 추가할지(공유 파일) 결정 필요.
- 리드: interfaces.md 3.2 `prd_se_resp` 설명 정정 요청(연 단위는 모두 `A`). `2년 -> F` 확정 반영.
- 리드: `data/logs/`가 .gitignore에 없음. 추가 검토 요청.
- ai-engineer: `load_meta()` 사용 시 `section`/`name_group`이 빈 경우가 있음(section 40, name_group 320). `units`가 빈 표 다수.
- 다음 작업: `src/kosis/fetch.py` (DataRequest -> DataResult), 수치 결측 표기 EDA를 새 14개 조사로 확대.

## 산출물 목록
- `src/meta/preprocess_population.py`, `src/meta/enrich_meta.py`, `src/meta/load.py`, `src/kosis/client.py`, `requirements.txt`
- `data/source/population.xls`, `data/processed/population_table_catalog.jsonl`, `data/processed/table_meta.jsonl`
- (미커밋) `data/processed/obj_values/*.json` 33MB
