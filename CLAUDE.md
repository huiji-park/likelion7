# 국가통계 AI 챗봇 및 맞춤형 통계 시각화 서비스

KOSIS 통계표 메타데이터 + OpenAPI 수치 데이터로 자연어 질문 → 통계표 탐색 → 수치 분석 → 요약 → 차트 → 출처 응답까지 수행하는 AI 서비스.
단계: 실전1(통계 수치 요약) → 실전2(통계표 안내 챗봇) → 종합(통합 챗봇 + 시각화 + 연속 대화).

## 에이전트 팀 (`.claude/agents/`)
| 에이전트 | 모델 | 담당 | 보고서 위치 |
|---|---|---|---|
| `project-lead` | Opus 5.5 | 작업 분해·위임, 인터페이스 계약, **진행 기록·최종 보고서** | `docs/progress.md`, `docs/final_report.md` |
| `data-engineer` | Sonnet 5.5 | 메타데이터 EDA·정제, KOSIS API 클라이언트, 수치 검증 | `docs/reports/data/` |
| `ai-engineer` | Sonnet 5.5 | 질의 분석, 통계표 검색, 수치 분석, HCX 요약, 연속 대화 | `docs/reports/ai/` |
| `eval-engineer` | Sonnet 5.5 | 기준 문서, 골든셋, 자동 평가, 실패 분석 | `docs/reports/eval/` |
| `service-engineer` | Sonnet 5.5 | 차트 생성, UI, 통합·시연 | `docs/reports/service/` |
| `stats-fact-checker` | Sonnet 5.5 | 수치·출처·금지 규칙·키 노출 검수 | `docs/reports/factcheck/` |

## 산출물 규칙
- 모든 팀원은 작업마다 보고서를 남긴다 (EDA·정제·설계·실험·평가·구현·검수 등). 보고서가 없으면 완료로 치지 않는다.
- 파일명: `docs/reports/<역할>/YYYY-MM-DD_<주제>.md`, 양식: `docs/reports/TEMPLATE.md`
- 진행 상황 기록(`docs/progress.md`)과 최종 보고서(`docs/final_report.md`)는 project-lead만 작성·수정한다. 팀원은 보고서 경로와 핵심 결과를 리드에게 전달한다.

## Git 작업 규칙
사용자가 GitHub 저장소를 관리한다. 팀원과 리드는 각자 브랜치에 푸시만 하고, **검수·PR·머지는 사용자가 한다.**

| 역할 | 브랜치 접두어 | 작업 폴더 (git worktree) |
|---|---|---|
| project-lead | `lead/` | `../likelion7-wt/lead` |
| data-engineer | `data/` | `../likelion7-wt/data` |
| ai-engineer | `ai/` | `../likelion7-wt/ai` |
| eval-engineer | `eval/` | `../likelion7-wt/eval` |
| service-engineer | `service/` | `../likelion7-wt/service` |
| stats-fact-checker | `factcheck/` | `../likelion7-wt/factcheck` |

1. **브랜치**: 작업 단위로 `<접두어>/<작업주제>`를 최신 `origin/main`에서 만든다 (예: `data/meta-eda`, `ai/table-search`).
2. **작업 폴더 분리**: 여러 팀원이 동시에 일하므로 같은 폴더에서 브랜치를 바꾸지 않는다. 자기 worktree에서만 작업한다.
   ```bash
   git fetch origin
   git worktree add ../likelion7-wt/data -b data/meta-eda origin/main   # 처음
   git -C ../likelion7-wt/data switch -c data/<다음주제> origin/main     # 다음 작업
   ```
   다른 역할의 worktree나 브랜치는 건드리지 않는다.
3. **금지**: `main`에 직접 커밋·푸시, 내 브랜치를 `main`이나 다른 사람 브랜치에 merge, force push, PR 생성·머지 (사용자가 요청한 경우만 예외).
4. **커밋 전 점검**: `git diff --cached`로 `.env`, API Key 문자열, `data/raw/`, `data/cache/`가 포함되지 않았는지 확인한다. 하나라도 있으면 커밋하지 않고 보고한다.
   ```bash
   git diff --cached | grep -inE 'api_?key|apikey=|secret|token' && echo "키 의심 → 커밋 중단"
   ```
   코드에서 키는 반드시 `os.environ["KOSIS_API_KEY"]`처럼 환경변수로 읽는다. URL·params에 키를 직접 쓰지 않는다.
5. **커밋 메시지**: `[역할] 요약` 형식 (예: `[data] 메타데이터 EDA 보고서 추가`). 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (리드) 또는 `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (팀원) 줄을 넣는다.
6. **한 브랜치 = 코드 + 보고서**: 푸시하는 브랜치에는 해당 작업의 보고서(`docs/reports/<역할>/...`)가 반드시 포함된다. 사용자는 이 보고서를 보고 검수한다.
7. **푸시 후 보고**: `git push -u origin <브랜치>` 후 리드에게 브랜치명, 커밋 요약, 보고서 경로를 전달한다. 리드는 `docs/progress.md`에 "리뷰 대기"로 기록한다.
8. **공유 파일**: `docs/interfaces.md`, `docs/progress.md`, `CLAUDE.md`, `.claude/` 는 리드 브랜치에서만 수정한다. `requirements.txt` 같은 공용 파일을 바꿔야 하면 변경을 최소화하고 보고서에 적는다.
9. **다른 팀원의 결과물**은 `main`에 머지된 것만 쓴다. 새 작업은 최신 `origin/main`에서 시작하고, 진행 중인 브랜치에 반영할 때는 `git fetch origin && git merge origin/main`을 쓴다 (rebase 후 force push 금지). 머지 전 결과가 필요하면 리드에게 알린다.

## 절대 규칙
- 실제 데이터에 없는 수치를 생성하지 않는다. 답변 불가 시 이유와 가능한 범위를 안내한다.
- 통계 수치·기간·단위·분류 기준을 일치시키고, 비교 불가하면 그 한계를 밝힌다.
- 모든 주요 수치는 원본 통계표(조사명/통계표명/tblId)까지 추적 가능해야 한다.
- 인과관계 단정, 정치적 주장, 근거 없는 정책 평가를 넣지 않는다.
- 수치 계산은 코드로 하고 LLM에게 맡기지 않는다.
- API Key(KOSIS, HCX)는 `.env`에만 둔다. 코드·로그·출력·커밋에 노출 금지. 유출 의심 시 즉시 담당자에게 공유.
- 결과물 외부 공개·재배포는 담당자 사전 확인 필요.

## 개발 환경
- Python 3.12, 환경변수: `KOSIS_API_KEY`, `HCX_API_KEY` (`.env.example` 참고)
- 데이터 범위: 14개 조사, 약 2,364개 통계표 (지역통계 제외)
