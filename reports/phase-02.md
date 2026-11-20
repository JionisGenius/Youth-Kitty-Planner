# Youth Kitty Planner (YKP) — Phase 2 구현·검증

- 작성일: 2026-11-19 KST
- 브랜치: `main`, 작업 트리 검증
- 상태: **PASS — F3005~F3011 Phase 2 범위**

## 구현 및 변경 파일

| 변경 | 파일 | 책임 |
|---|---|---|
| 신규 | `backend/app/schemas/agent.py`, `backend/app/agents/state.py` | 사용자 조건, AgentState, WorkflowStep, 판정, 출처, PlanDraft |
| 신규 | `backend/app/agents/{graph,planner,memory}.py` | LangGraph 실행, GMS 분석·Tool 계획, SQLite 세션 체크포인트 |
| 신규 | `backend/app/services/{constraint_patch,constraint_engine,replan_policy}.py` | 원문 대조, 예산·일정 판정, 사용자 허용 범위·재계획 상한 |
| 신규·수정 | `backend/app/core/gms.py`, `scripts/verify_gms_preflight.py` | Phase 1의 Responses API 연결·파싱을 공용 모듈로 추출하여 양쪽에서 재사용 |
| 수정 | `requirements.txt`, `.env.example` | SQLite checkpointer 3.1.3과 빈 GMS 환경변수 예시 |
| 신규 | `tests/integration/test_agent.py`, `reports/phase-02.md` | 반복 가능한 그래프 테스트 및 실제 실행 기록 |

GMS가 조건과 근거 구절을 추출하고 Registry의 함수 명세로 선행 Tool을 선택한다. 서버가 사용자 원문과 Pydantic 입력을 검증한 뒤 지역 해석, 실거래, 후보 지번 해석, 표제부를 필요한 순서로 연결한다. 같은 실행의 동일 Tool 인자는 캐시에서 재사용한다. SQLite에는 세션별 사용자 조건과 계약월을 저장한다. 원본 채팅, 실행 결과, 캐시와 오류는 일시 상태에서만 사용한다. 세션을 바꾸면 별도 조건으로 시작한다. 기존 Tool DTO·Provider 및 FastAPI 경로 설계는 유지했다.

## 요구사항별 증거

| 요구사항 | 상태 | 실행 증거 |
|---|---|---|
| F3005 의도·조건 | PASS | 실제 GMS 생성·수정·일반 의도. Mock에서 누락 질문·잘못된 금액 근거 거부 |
| F3006 도구 계획 | PASS | GMS 함수 선택, 서버의 Pydantic·인자 범위 검증, 일반 질문에서 계획·도구 0회 |
| F3007 실행·통합 | PASS | 실제 전월세·카카오·건축HUB 실행. Mock에서 후보 ID 전파, 표제부 실패와 정상 거래 분리 |
| F3008 제약 검증 | PASS | 보증금·월세 정수 원화와 상한 비교, 준비 종료일과 출근일 비교, 미확인 자료 UNKNOWN |
| F3009 재계획 | PASS | 승인 지역 또는 더 넓은 조회 건수, 최초 시도 이후 최대 3회, 중복 차단·캐시. 인증·필수 스키마 오류에서 재호출 없음 |
| F3010 Memory | PASS | 실제 월세만 변경. Mock에서 SQLite 재개, 다른 조건 유지, 세션 격리 및 메시지 미저장 |
| F3011 최종 응답 | PASS | 근거와 출처가 있는 실제 초안, 건물 및 현재 임대 가능 여부 UNKNOWN 처리, 계약·금융 안내 |

## 반복 테스트

| 명령 | 종료 및 결과 |
|---|---|
| `.venv/Scripts/python -m pytest -q tests/integration/test_agent.py` | 0, 15 passed |
| `.venv/Scripts/python -m pytest -q --ignore=tests/integration/test_agent.py` | 0, 기존 37 passed |
| `.venv/Scripts/python -m pytest -q` | 0, 52 passed |
| `.venv/Scripts/python -m pip check` | 0, 의존성 충돌 없음 |

새 시나리오 테스트는 실제 LangGraph와 SQLite를 실행하고 GMS·외부 Tool 결과를 Mock으로 공급한다. 정상 초안, 월세 초과 후 대안, 모든 대안 실패와 3회 상한, 표제부 타임아웃, 일반 대화, 월세만 수정 후 세션 격리를 모두 검증했다. 위조 시군구 인자, 중복 전략, 호출 캐시, 일정 충돌, 인증·스키마 장애도 확인했다.

보안 검사에서 실제 환경 키 4종과 인코딩 변형을 커밋 후보 텍스트 43개와 대조해 노출 0건을 확인했다. `git check-ignore`에서 `.env`와 기본 SQLite 체크포인트 경로의 제외를 확인했다.

## 실제 GMS 및 외부 API 실행

`.venv/Scripts/python -`으로 기본 `open_agent()`를 임시 SQLite 파일에 연결하고 세 턴을 동일 세션에서 실행했다. 종료 코드 **0**이었다. 아래는 GMS와 실제 외부 API를 사용한 결과이며 Mock 건수에 포함하지 않는다.

| 턴 | 의도 / 상태 | 외부 Tool | 관찰 |
|---|---|---|---|
| 1. 독립 준비 | CREATE_PLAN / PARTIAL · 13,922 ms | 전월세·카카오·표제부 성공 | 계획 초안 생성. 준비 기간·보증금·월세 PASS, 건물·현재 매물 여부 UNKNOWN |
| 2. 월세만 변경 | UPDATE_CONSTRAINT / PARTIAL · 8,985 ms | 같은 세 Tool 성공 | 월세만 변경. 보증금·출근일 유지. 계획 초안 생성 |
| 3. 사용법 | GENERAL / SUCCEEDED · 3,921 ms | 0회 | 일반 안내 반환 |

도구가 정상 응답했어도 표제부 증거가 충분하지 않으면 건물 판정은 UNKNOWN이다. 정상 결과의 세 출처를 확인했고, 소요 시간은 각 턴의 전체 실행 시간이다. 이번 그래프 실행에서는 개별 HTTP 상태와 원본 응답을 보관하지 않았다. [Phase 1 HTTP 증거](evidence/phase-01-http.md)

재현하려면 레포 루트의 가상환경 Python에서 아래를 실행한다. 출력에는 상태와 Tool 이름만 포함된다.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backend.app.agents.memory import open_agent

with TemporaryDirectory() as tmp, open_agent(Path(tmp) / "memory.sqlite3") as agent:
    session = agent.new_session_id()
    for message in (
        "서울 종로구(11110)에서 독립 준비 계획을 세워줘. 2025년 1월 실거래를 참고하고, 보증금 5억원, 월세 300만원 이하로 찾아줘. 준비 시작일 2026-11-20, 준비 기간 7일, 출근일 2026-12-01.",
        "월세만 280만원 이하로 바꿔줘.",
        "이 플래너는 어떻게 쓰나요?",
    ):
        result = agent.run(session, message)
        print(result.get("intent"), result["execution_status"], result["changed_fields"],
              [(step.tool_name, step.status) for step in result["workflow_steps"]])
```

## 남은 범위

- 관리비·통근시간·현재 매물 여부는 근거가 없으면 UNKNOWN이다. 날짜·지역이 불분명하거나 단독 건물 질의에 대조 후보가 없으면 확인을 요청한다. 실거래는 과거 계약 사례다.
- SQLite 세션 인증·소유권·삭제 정책, 실행 이벤트 저장, 계획 저장 및 REST API는 Phase 3 범위다. 외부 API 계정별 쿼터와 공식 일정은 이전 [Phase 1 보고서](phase-01.md)의 확인 항목으로 남아 있다.

REVIEW REQUIRED — 다음 단계 미착수
