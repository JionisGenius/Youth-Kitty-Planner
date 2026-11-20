# Youth Kitty Planner (YKP) — Phase 3 구현 및 검증

- 작성일: 2026-11-20 KST
- 브랜치: `main`
- 구현 및 통합 검증: **PASS — F3012~F3017**
- GMS를 포함한 전체 실연동 재검증: **BLOCKED — GMS HTTP 429**. 실제 외부 데이터 API와 Mock GMS를 결합한 FastAPI 저장 흐름은 별도로 통과했다.

## 구현 및 파일

| 경로 | 구현 |
|---|---|
| `backend/app/db/{connection.py,schema.sql,repositories/}` | 기존 7개 테이블, SQLite FK·인덱스·제약, 세션·실행·계획 저장소, 쓰기 트랜잭션 |
| `backend/app/events/{publisher,logging_agent}.py` | 구조화 이벤트 발행 및 독립 SQLite 구독자 |
| `backend/app/agents/{graph,memory}.py` | 기존 LangGraph 단계와 Tool 결과에 이벤트 연결, 인증 세션과 thread ID 연결 |
| `backend/app/{main.py,api/}`, `backend/app/core/errors.py`, `backend/app/schemas/{api,events}.py` | FastAPI, Bearer 인증, 기존 REST 경로·Pydantic·OpenAPI 및 공통 오류 |
| `backend/app/services/provenance.py` | 소유한 실행의 서버 발급 출처 참조만 저장. 동일 조건·기간에 해당하는 판정만 복사 |
| `tests/integration/test_api.py`, `requirements-dev.txt` | TestClient 통합 테스트 15개와 HTTPX 개발 의존성 |

서버에서 무작위 256비트 토큰을 만들고 SHA-256 해시를 저장한다. 토큰은 생성 응답에서만 제공한다. 세션은 24시간 고정 만료이며 다음 세션 발급 시 별도 소유권과 Memory를 갖는다. Memory DB와 비즈니스 DB는 별도 파일이다. 로그 삭제는 이벤트·실행 기록을 삭제하며, 보존된 계획의 실행 참조를 NULL로 처리한다. 계획 삭제는 Task·출처·평가를 함께 삭제한다.

시간은 UTC로 저장하고 작업 날짜를 한국시간으로 검증한다. 실제 시간 구간이 겹치면 동일 소유자의 같은 계획 및 다른 계획에서 경고를 반환하며 저장은 성공한다. 자정을 넘는 작업도 실제 겹치는 시간으로 비교한다. 시간이 미정인 작업은 시작·종료를 NULL로 유지한다. PATCH는 안정적인 작업 ID와 add/update/delete 연산을 사용한다. 이전 revision을 보낸 동시 요청은 409로 거부한다.

기존 내부 초안의 category는 유지하고 공개 API·DB에서는 설계의 `FIRST_JOB_INDEPENDENCE`로 변환한다. 실행에 연결된 출처는 서버가 확인한 참조만 허용한다. 조건·기간이 서명된 판정 범위와 같은 경우 평가를 저장하며, 상한값은 저장된 계획 조건에서 채운다. 외부 원본 관측값은 영속 이벤트에 보관하지 않아 저장된 평가의 observed 값은 NULL로 남는다.

## 요구사항별 검증

| 요구사항 | 상태 | 실행 증거 |
|---|---|---|
| F3012 이벤트 발행 | PASS | 13종 이벤트를 그래프·도구·실행 종료 테스트에서 확인. 단계별 순번·소요 시간과 안전한 GMS 의도 요약 포함 |
| F3013 Logging Agent | PASS | 발행된 정제 payload와 저장·조회 payload 일치, 소비 중 추가 LLM 호출 0회. 구독자가 없거나 예외를 내도 Main Agent 대화 성공 |
| F3014 로그 관리 | PASS | 목록·상세·삭제, 세션 소유권, 실행 시작·순번 정렬, PATCH 405와 OpenAPI 부재, DB UPDATE 차단 |
| F3015 계획 저장·조회 | PASS | 비즈니스 DB 및 재시작 후 조회, Task 날짜·NULL 시각, 계획 내·계획 간 중복 저장 201 + 경고 |
| F3016 계획 수정·삭제 | PASS | 작업 추가·수정·삭제, 트랜잭션 롤백, 동시 요청 200/409, 교차 세션 차단과 종속 레코드 삭제 |
| F3017 FastAPI 연동 | PASS | 확정 경로·OpenAPI, Bearer/만료, 실제 LangGraph 실행 및 같은 세션 Memory. Mock 통합과 외부 데이터 실호출 혼합 검증 통과 |

## 테스트 및 실호출

| 실행 | 종료 코드 / 결과 |
|---|---|
| `.venv/Scripts/python -m pytest -q --ignore=tests/integration/test_api.py` | 0 / 기존 52개 통과 |
| `.venv/Scripts/python -m pytest -q --tb=short` | 0 / 전체 67개 통과. 신규 15개는 TestClient·LangGraph·실제 로컬 SQLite, GMS·데이터 API Mock |
| `.venv/Scripts/python -m pip check` | 0 / 의존성 충돌 없음 |
| 실제 GMS + 실제 데이터 API 구성으로 `TestClient`의 세션·대화 요청 | 1 / 익명 세션 발급 성공, 대화 HTTP 502 및 안전 코드 RATE_LIMITED. 이후 데이터 단계 성공으로 집계하지 않음 |
| `.venv/Scripts/python -m scripts.verify_gms_preflight` | 1 / 설정 모델 연결 검증에 HTTP 429. 공급자의 한도 원인이나 해제 시점은 미확인 |
| `.venv/Scripts/python -m scripts.verify_external_apis --match` | 0 / 카카오 HTTP 200, 전월세 HTTP 200·000, 건축HUB HTTP 200·00. 실제 연결 양성 1건, 미확인 2건 |
| TestClient + Mock GMS 계획 + 실제 데이터 API 3종 | 0 / 대화 HTTP 200, PARTIAL, Tool 3종 정상 처리, 정렬된 이벤트 25건. 계획 저장 201·재조회 200, 작업 2건·출처 22건·평가 5건 |

Windows 기본 샌드박스에서는 Python의 TestClient 이벤트 루프가 내부 루프백 소켓 생성에서 멈췄다. 스택으로 위치를 확인한 후 루프백 허용 환경에서 Mock 회귀를 실행했다. 전체 실연동 502는 공급자 429를 사용자에게 원문 없이 전달한 결과다. 혼합 검증의 PARTIAL은 건물 일치 미확인을 품고 정상 거래 근거를 보존한 결과다.

보안 검증은 실제 키 4종과 인코딩 변형을 Git 후보 텍스트 59개와 대조했고 검출 파일은 0개였다. `.env`와 두 SQLite 경로는 Git 제외를 확인했다.

레포 루트에서 `.venv/Scripts/python -m uvicorn backend.app.main:app`으로 실행한다. OpenAPI는 `/docs`와 `/openapi.json`에서 확인할 수 있다. 기본 파일은 Git 제외 경로의 `backend/data/ykp.sqlite3`와 `backend/data/agent-checkpoint.sqlite3`다.

## 남은 범위

- GMS HTTP 429 해소 후 실제 모델을 포함하는 Phase 3 전체 연결을 재검증할 수 있다. 로깅이 중단된 실행은 대화 응답을 유지하되, 저장되지 않은 출처가 포함된 계획을 저장할 때는 그 출처를 증명할 수 없다.
- 만료 후 이전 세션을 회수하는 기능과 데이터 보존·삭제 운영 정책은 현재 API 계약 범위 밖이다. UI, 실시간 SSE, 화면 검증은 미착수다.

REVIEW REQUIRED — 다음 단계 미착수
