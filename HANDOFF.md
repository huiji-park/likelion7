# 작업 인계 (HANDOFF)

> 마지막 갱신: 2026-10-22 · 새 세션은 이 파일 → `CLAUDE.md` → `docs/progress.md` → `docs/interfaces.md` 순서로 읽는다. 답변은 한국어.

## 1. 현재 상태
- 사전 점검 3개 완료: KOSIS API, Python 3.12(uv), HCX API(CLOVA Studio v3, HCX-005·HCX-DASH-002·HCX-007 접근 확인).
- **기준 메타데이터 = 사용자 제공 인구 카탈로그** `population_table_catalog.jsonl` (2,364표·14개 조사·기관 5곳). 이전 `data/census-eda`의 1,901표 정제본은 쓰지 않는다.
- 인터페이스 계약 `docs/interfaces.md` v0.3.

## 2. 브랜치 (모두 푸시 완료, 검수·머지는 사용자)
| 브랜치 | 내용 | 상태 |
|---|---|---|
| `lead/interfaces` | interfaces v0.3, progress.md, `.gitignore`(data/logs, obj_values), 이 파일 | 리뷰 대기 — **먼저 머지 필요** |
| `data/catalog-import` | 카탈로그·원본 xls, 전처리·getMeta 보강·`load_meta()`, `table_meta.jsonl`, 보고서 | 리뷰 대기 — **먼저 머지 필요** |
| `factcheck/census-eda` | 이전 EDA 검수 보고서 (조건부 통과) | 참고용 |
| `data/census-eda` | 이전 인구총조사 EDA | 머지 보류 (기준 제외) |
| `data/api-check` | 초기 수치 조회 스크립트 | 리뷰 대기 |

## 3. 결정 사항
- 검색 대상 2,364표 전체, 골든셋 정답 표는 인구총조사 1,876표 안에서만.
- `data/processed/obj_values/`(33MB)는 비커밋, `python -m src.meta.enrich_meta`로 재생성(캐시 있으면 수 분).
- 요약 기본 모델 HCX-005 (비교 실험은 ai-engineer).

## 4. 다음 할 일
1. 위 두 브랜치 머지 확인 후 팀원 작업 시작 (팀원은 main 머지분만 사용).
2. eval-engineer: 질문 유형·답변 가능/불가 기준 문서 + 골든셋 초안.
3. data-engineer: `src/kosis/fetch.py` (DataRequest→DataResult, 40,000셀 분할, `-`/0 구분).
4. ai-engineer: 질의 분석·통계표 검색(실전2), HCX 연동.

## 5. 환경 메모
- `python`은 Store 스텁 → `py -3.14` 또는 worktree의 `.venv/Scripts/python.exe`(3.12, uv).
- 키: 메인 폴더 `.env`의 `KOSIS_API_KEY`, `HCX_API_KEY`. worktree에서는 `KOSIS_ENV_PATH`로 지정. 값 출력 금지.
- worktree: `../likelion7-wt/{lead,data,factcheck}`. 로컬 캐시 `../likelion7-wt/data/data/cache/`(2,364표 getMeta 포함).
- 메인 폴더 `main`에 사용자 파일(Dense_Retriever.py 등)이 staged 상태로 남아 있음 — 사용자 소관, 건드리지 않음.
