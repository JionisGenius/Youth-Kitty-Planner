# Youth Kitty Planner (청년냥이 플래너, YKP) — 폴더 구조 설계 v1.0

- 상태: **신규 프로젝트 기준 권장 구조 / 실제 레포 구조는 아직 확인되지 않음**
- 적용 범위: SSAFY AI 코어 프로젝트 3회차 F3001~F3019, NF3001~NF3007
- 최우선 외부 기준: `AI코어프로젝트_3회차_요구사항정의서(4).pdf`
- 동료 문서: `docs/ARCHITECTURE_AND_SCHEMA_v1.md`, `CODEX_START_HERE.md`
- 브랜딩: 영문 **Youth Kitty Planner**, 한국어 **청년냥이 플래너**, 약칭 **YKP**, 슬로건 **Your Smart Guide to Life in Korea**
- **기존 코드의 변수명, API 경로, DB 식별자는 브랜딩만을 이유로 변경하지 않는다.**

## 1. 디렉터리 트리 (신규 레포 기준)

아래는 **목표 구조이지 이미 생성된 폴더가 아니다.** 신규 레포는 이를 사용한다. 기존 레포에서는 Phase 0에서 먼저 실제 구조를 조사하고, 기능을 깨지 않는 최소 변경안과 차이표를 보고한다. 기존 폴더·코드 무단 이동이나 삭제 금지.

```text
YKP/                                  # Git 저장소 루트 (디렉터리 이름은 기존 저장소 이름 유지 가능)
├── README.md                          # 서비스 소개, 실행·API 키 설정, 제출 안내
├── .gitignore                         # .env, DB, Checkpointer, 캐시, 빌드 결과 제외
├── .env.example                       # 변수 이름/예시만, 실제 비밀정보 금지
├── CODEX_START_HERE.md                # Phase별 구현 지시 및 승인 게이트
├── backend/
│   ├── pyproject.toml                 # Python 패키지/의존성(기존 requirements.txt 사용 시 유지)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI 앱 생성, 라우터/오류 처리 등록
│   │   ├── core/
│   │   │   ├── config.py              # 환경변수 로드, URL·타임아웃 설정
│   │   │   ├── security.py            # 세션 토큰 해시·소유권·민감정보 정책
│   │   │   └── errors.py              # 공통 안전 오류 코드/핸들러
│   │   ├── api/
│   │   │   ├── dependencies.py        # 인증된 세션/DB 의존성
│   │   │   └── v1/
│   │   │       ├── sessions.py        # POST /api/v1/sessions
│   │   │       ├── chat.py            # POST /api/v1/chat
│   │   │       ├── plans.py           # 계획 CRUD
│   │   │       ├── logs.py            # 로그 목록·상세·삭제
│   │   │       ├── runs.py            # 실행 이벤트 조회
│   │   │       └── health.py          # GET /api/v1/health
│   │   ├── schemas/                   # Pydantic 공개 DTO 및 내부 표준 DTO
│   │   │   ├── common.py             # Enum, ApiError, 공통 검증
│   │   │   ├── constraints.py        # UserConstraints, LocationCondition
│   │   │   ├── tools.py              # ToolSuccess/ToolFailure, WorkflowStep
│   │   │   ├── plans.py              # PlanDraft, PlanCreate/Update/Read
│   │   │   ├── chat.py               # ChatRequest/Response, SessionCreated
│   │   │   └── events.py             # AgentEvent, 실행 상태 DTO
│   │   ├── agents/
│   │   │   ├── state.py              # AgentState와 run별 상태 초기화
│   │   │   ├── graph.py              # LangGraph 노드 연결, 조건부 라우팅
│   │   │   ├── nodes/                # analyze, validate, plan, execute,
│   │   │   │                         # normalize, evaluate, replan, respond
│   │   │   └── memory.py             # thread/checkpointer 관리, patch merge
│   │   ├── tools/
│   │   │   ├── registry.py           # Tool 화이트리스트 및 스키마 등록
│   │   │   ├── executor.py           # Tool 호출/응답/오류/재시도
│   │   │   └── providers/
│   │   │       ├── kakao_local.py     # 주소·장소 검색 외부 API 클라이언트
│   │   │       ├── molit_rent.py      # 연립다세대 전월세 과거 거래 조회
│   │   │       └── building_hub.py    # 건축HUB 건축물대장 조회
│   │   ├── services/
│   │   │   ├── normalize.py          # provider 응답 → 내부 DTO 변환
│   │   │   ├── building_match.py     # 후보→건물 매칭/불명확 처리
│   │   │   ├── constraint_engine.py  # PASS/FAIL/UNKNOWN 규칙 계산
│   │   │   ├── replan_policy.py      # 재계획 상한·고정 제약 보호
│   │   │   ├── overlap.py            # 같은 날짜 시간 겹침 경고
│   │   │   └── cache.py              # 요청 범위 캐시, 필요 시 영속 캐시
│   │   ├── events/
│   │   │   ├── publisher.py          # 구독자에 의존하지 않는 이벤트 발행
│   │   │   └── logging_agent.py      # LLM 없이 원본 이벤트 구독·저장
│   │   └── db/
│   │       ├── connection.py         # SQLite 연결/트랜잭션/FK on
│   │       ├── models.py             # sessions, plans, plan_tasks, agent_runs,
│   │       │                         # run_events, sources, evaluations, cache
│   │       └── repositories/         # DB 접근: sessions, plans, logs 등
│   └── data/                          # 런타임 SQLite/Checkpointer 저장 경로, Git 제외
├── frontend/
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── api/                     # FastAPI HTTP 클라이언트
│       ├── views/                   # PlannerView, MyPlansView, RunLogView
│       ├── components/              # 입력, 결과, Task, Agent 단계, 경고 UI
│       ├── stores/                  # 세션·조건·계획 상태
│       └── assets/                  # YKP 브랜딩/고양이 마스코트(후속)
├── tests/
│   ├── unit/                        # 스키마·제약·매칭·충돌·캐시·재계획
│   ├── integration/                 # 실제 API(옵트인), FastAPI·DB·Memory·Logging
│   └── fixtures/                    # 키와 식별정보 제거한 mock/sample
├── scripts/
│   └── verify_external_apis.py      # 세 API 실제 호출 검증; 비밀정보 출력 금지
├── docs/
│   ├── ARCHITECTURE_AND_SCHEMA_v1.md
│   ├── PROJECT_STRUCTURE_YKP.md      # 현재 문서
│   └── PHASE_REPORT_TEMPLATE.md
└── reports/
    ├── phase-01.md                  # Codex가 Phase 0~1 이후 작성
    └── evidence/                    # 테스트 출력, 비밀 제거한 API 응답 구조
```

파일 이름은 예시이며 기능 경계가 중요하다. 빈 파일을 대량 생성할 필요는 없다. 구현한 Phase에 필요한 파일만 만들고, 기존 프로젝트에 이미 유사 책임의 파일이 있으면 재사용한다.

## 2. 의존성 방향 및 책임 규칙

1. **Frontend → FastAPI API → 서비스/Agent → Tool provider/DB** 방향으로 의존한다. Vue에서 카카오/국토부 인증키를 직접 쓰지 않는다.
2. `api/v1/*` 라우터는 인증·입출력·HTTP 상태에 집중하고, 외부 HTTP 호출이나 LLM 프롬프트 로직을 직접 구현하지 않는다.
3. `agents/graph.py`가 노드 순서와 조건부 분기를 관리하며, `agents/nodes`는 공유 `AgentState`의 명시된 필드만 갱신한다. `agents/memory.py`는 Checkpointer와 조건 patch-merge 담당이다.
4. `tools/providers/*`는 **실제 외부 HTTP 통신**, `services/normalize.py`는 제공기관별 결과를 내부 DTO로 변환한다. `tools/registry.py`는 Tool 이름·설명·입출력 스키마 등록만 담당한다. `tools/executor.py`는 호출과 실패 처리를 담당한다.
5. `services/constraint_engine.py`, `building_match.py`, `overlap.py`의 판정과 계산은 **결정적 코드**로 구현하며 LLM을 호출하지 않는다.
6. `events/publisher.py`는 구독자 없이도 동작하도록 하고, `events/logging_agent.py`는 **별도 모듈**에서 이벤트 원본을 수집·저장한다. 수집/저장에 LLM을 호출하지 않는다. `db/repositories`를 통해 로그를 저장하며 Main Agent가 로깅 오류로 중단되지 않아야 한다.
7. `schemas/*`는 Pydantic 입력/출력 계약, `db/models.py`는 영속 DB 레코드, `agents/state.py`는 실행 상태를 담당한다. 세 유형을 하나의 범용 객체로 합치지 않는다.
8. API 키는 루트 `.env` 또는 기존 비밀 설정에만 저장한다(추적 제외). `.env.example`은 가짜 값/변수명만 포함. Checkpointer DB, SQLite, 실행 로그 원본, 실제 API JSON 덤프, 빌드 산출물은 Git에서 제외하거나 민감정보 제거 정책을 먼저 적용한다.
9. 외부 API 응답의 필드명·연결 키는 Phase 1 **실제 호출 성공 뒤** 확정한다. 미검증 필드를 강제로 매핑하거나 현재 매물/계약 안전을 확정하지 않는다.
10. 제출 증거는 `reports/evidence/`, 테스트는 `tests/`, 설계와 요구사항은 `docs/`로 통일한다. 파일 경로가 바뀌면 보고서에 명시한다.

## 3. Phase별 폴더 소유권

| Phase | 작업 폴더 | 필수 산출물 |
|---|---|---|
| 0 | 레포 전체 조사, `docs/` | 실제 구조와 목표 구조 차이·변경안 보고 |
| 1 | `backend/app/tools/`, `schemas/tools.py`, `services/normalize.py`, `services/building_match.py`, `scripts/`, `tests/` | 3 API 실제 응답·Tool 스키마·성공/실패 테스트 |
| 2 | `backend/app/agents/`, `services/constraint_engine.py`, `services/replan_policy.py`, `services/cache.py`, `tests/` | LangGraph·Memory·제약 판정·최대 3회 재계획 |
| 3 | `backend/app/db/`, `backend/app/events/`, `backend/app/api/`, `schemas/`, `tests/` | FastAPI·계획 CRUD·로깅 Agent·중복 경고·소유권 보호 |
| 4 | `frontend/`, `tests/`, `README.md`, `reports/` | 대화·계획 화면·실행 과정 표시·최종 요구사항 증거 |

공용 스키마·설정·API 진입점은 단계에 따라 일찍 필요할 수 있다. 단계 구분은 기능 완료 게이트이지 import를 위한 최소 파일 생성 금지가 아니다.

## 4. Codex Phase 0 구조 확인 게이트

Codex는 코드를 생성하기 전에 다음을 `reports/phase-01.md`의 구조 점검 항목에 기록해야 한다.

- 실제 디렉터리 트리(최상위 및 핵심 모듈), 기존 실행 명령, 현재 브랜치.
- **기존 구조를 유지할지 / 새 구조를 채택할지** 와 사유.
- 구조 차이표: 목표 경로, 실제 경로, 처리(`그대로 사용 / 추가 / 변경 제안`), 영향 범위.
- API/Agent/DB/UI/Tests 책임 분리가 충족되는지와 NF3006 영향.
- `.env`, SQLite DB, Checkpointer, 테스트 응답 샘플 등 비밀·데이터 파일의 `.gitignore` 점검.
- 아직 생성하지 않은 폴더나 파일은 `NOT_STARTED`로 기록. 파일 목록만으로 기능 PASS 처리 금지.

구조를 바꾸기 위해 기존 코드를 대량 이동해야 하거나 import/API 호환성이 깨진다면, Phase 0 보고서에 변경안을 기록하고 무단 재구성하지 않는다.

## 5. 폴더 구조와 브랜딩 변경 규칙

- 모든 사용자 표시 이름/README/화면/발표 자료는 **Youth Kitty Planner / 청년냥이 플래너 (YKP)**로 통일한다.
- Git 저장소 폴더, Python 패키지/모듈 식별자, FastAPI 경로, DB 테이블 이름은 **표시용 브랜드 변경만을 이유로 수정하지 않는다.**
- 마스코트 이미지 제작, 밈 문구, 색상 테마는 **3일 MVP 필수 구현 이후** 진행할 수 있다. 기능의 검증 가능성보다 우선하지 않는다.
- 문서 간 불일치가 생기면 **공식 PDF 요구사항 > ARCHITECTURE_AND_SCHEMA_v1.md의 기능/데이터 계약 > 이 폴더 구조의 모듈 배치 제안** 순서로 판단하고 보고한다.
