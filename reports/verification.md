# Youth Kitty Planner 제출 검증

공식 [셀프 체크리스트](../셀프체크리스트.xlsx)는 필수 **27/27**, F3020 포함 **통과 28개**, 실패 0개, 미확인 0개, 해당없음 4개입니다. 23번(대기 적정성)과 27번(제출 자료·기획 검증)은 2026-11-20 제출자의 직접 확인을 반영했습니다. 각 문항의 실행 원본과 화면은 [evidence/](evidence/)와 체크리스트 H열에 연결했습니다.

도메인은 첫 독립 준비입니다. 예를 들어 “종로구, 보증금 3,000만원, 월세 45만원, 출근 전 준비 7일”로 요청하면 세 외부 API의 정보를 참고해 일정·장소·예산·근거가 있는 계획을 생성하고 작업 목록을 저장합니다. 과거 신고 거래로 현재 매물 여부를 판단하지 않습니다. [요구사항 추적·Agent 설계·REST API 명세](../YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md) · [Tool 등록 명세](evidence/phase-01-tool-specs.json)

## 필수·심화 기능

| 요구사항 | 확인 결과 |
|---|---|
| F3001 Tool 등록·검증 | 세 외부 Tool의 이름·입출력 DTO·표준 오류를 검증했습니다. 잘못된 입력·키 누락을 안전하게 처리합니다. [등록·오류 테스트 화면](evidence/checklist-01-tool-validation.png) |
| F3002 과거 전월세 조회 | 계약월 기본값·미래월 처리, 시군구·계약월 조회, 보증금·월세 원화 정수 변환을 확인했습니다. [실제 호출](evidence/phase-01-live.jsonl) |
| F3003 건물 상세 | 주소·필지를 통해 후보를 추적하되 이름 등 증거가 부족하면 UNKNOWN으로 분류합니다. [건물 대조](evidence/phase-01-live.jsonl) |
| F3004 장소 검색 | 주소·키워드 정상 조회와 결과 없음·인증 실패를 확인했습니다. [HTTP 결과](evidence/phase-01-http.md) |
| F3005 의도와 조건 | 조건 추출과 누락 보존을 확인했습니다. [Agent 실행](evidence/checklist-06-agent-scenarios.png) |
| F3006 Tool 계획·순서 | GMS Tool Calling 3종과 Pydantic 인자를 검증했습니다. 일반 대화는 Tool 호출이 없습니다. [실제 GMS 로그](evidence/phase-01-gms.jsonl) |
| F3007 실행·통합 | 후보 ID를 후속 Tool에 전달하고 표제부 실패 시 거래 근거를 유지합니다. [부분 실패 로그](evidence/day-03-scenarios.json) |
| F3008 제약 평가 | 예산·기간의 PASS·FAIL·UNKNOWN과 역산 기준을 검증했습니다. [제약 계산](evidence/checklist-judgment.png) |
| F3009 재계획 | 승인 대안과 조회 범위를 적용합니다. 동일 결과를 캐시하고 최대 3회에 종료합니다. [실제 종료](evidence/checklist-23-live-result.png) |
| F3010 Memory | 같은 세션 후속 요청에서 월세만 바꾸고 다른 조건을 유지했습니다. SQLite Checkpointer를 통한 세션 격리·재개를 검증했습니다. [Agent 실행](evidence/checklist-06-agent-scenarios.png) |
| F3011 최종 답변 | 선택·제외 이유, 출처, 신고월, 현재 매물·건물 확인 한계를 표시합니다. [추천](evidence/checklist-12-recommendation.png) · [계약·금융 안내](evidence/checklist-judgment.png) |
| F3012 이벤트 발행 | 단계·Tool·재계획·종료 이벤트 순서와 소요 시간, 안전한 판단 근거를 확인했습니다. [이벤트 화면](evidence/checklist-14-agent-events.png) |
| F3013 Logging Agent | 발행·저장 payload 일치, 저장 중 LLM 호출 0회, 저장 예외가 채팅으로 전파되지 않는 것을 확인했습니다. [로깅 테스트](evidence/checklist-14-agent-events.png) |
| F3014 로그 관리 | 세션별 조회·삭제와 순서·소유권을 확인했습니다. 수정 API는 제공하지 않습니다. [Swagger](evidence/checklist-docs.png) |
| F3015 계획 저장·조회 | 작업 날짜·미정 시각, 재시작 후 조회, 일정 충돌 저장과 경고를 확인했습니다. [계획 관리](evidence/checklist-19-plan-crud.png) |
| F3016 계획 수정·삭제 | 리비전 충돌 409와 작업 변경·삭제, 종속 레코드 정리를 확인했습니다. [삭제 후 화면](evidence/checklist-20-plan-deleted.png) |
| F3017 FastAPI 연동 | Bearer 인증·만료, 채팅, 계획 CRUD, 이벤트 조회를 검증했습니다. [Swagger](evidence/checklist-docs.png) |
| F3018 Vue UI 연동 | 플래너·내 계획·실행 기록의 실제 REST 흐름을 확인했습니다. [Mock 시연](evidence/day-03-mock-chat.png) |
| F3019 실행 과정·오류 표시 | 처리 중 대기 안내, 완료 뒤 순서대로 표시하는 타임라인, 호출 제한·키 누락 안내를 확인했습니다. [대기](evidence/checklist-23-live-wait.png) · [타임라인](evidence/checklist-22-replan-timeline.png) · [키 누락](evidence/checklist-api-key.png) |
| F3020 이상 징후 판정 | 이벤트 기록에 기반해 중복 호출·재계획 초과·계획 외·누락 실행을 탐지합니다. 정상과 증거 부족은 추가 GMS 호출 0회, 이상에만 진단 1회입니다. 실제 GMS 분류 `WORKFLOW_DISPATCH`와 Mock HTTP 429 장애 격리를 확인했습니다. [실행 증빙](evidence/checklist-28-anomaly.png) |
| F3021~F3023 | 해당없음. 선택 심화 범위는 F3020입니다. |

Vue는 FastAPI를 통해 LangGraph를 실행합니다. Main Agent는 외부 Tool을 호출하고 이벤트를 발행합니다. Logging Agent는 이벤트를 정제·저장합니다. F3020은 저장된 같은 실행의 이벤트를 규칙과 대조한 뒤 종료 이벤트와 응답에 상태를 덧붙입니다.

## 비기능 요구사항

| ID | 결과 | 확인 근거 |
|---|---|---|
| NF3001 | 통과 | 환경변수·Git 제외 규칙·실제 비밀값 및 인코딩 변형 검사. [보안 점검](evidence/phase-01-security.md) |
| NF3002 | 통과 | 인증·호출 제한·입력 오류에서 원본 예외·키 비노출. [오류 화면](evidence/checklist-23-live-error.png) |
| NF3003 | 통과 | 개별 Tool 실패에도 부분 결과 유지. Logging Agent 오류가 Main Agent를 중단시키지 않음. [부분 실패](evidence/day-03-scenarios.json) |
| NF3004 | 통과 | 순서와 캐시, 실제 재계획 최대 3회 종료. [재계획 화면](evidence/checklist-23-live-result.png) |
| NF3005 | 통과 | Chrome에서 실제 지연을 측정했고, 제출자가 대기 적정성을 직접 확인했습니다. [측정 화면](evidence/checklist-23-measurements.png) |
| NF3006 | 통과 | 별도 Vue·FastAPI 실행, Agent·Tool·로깅·저장 모듈 분리. [구조](../YKP_codex_handoff_v1/docs/PROJECT_STRUCTURE_YKP.md) |
| NF3007 | 통과 | 공식 이용 조건 및 실제 계정 승인·한도·카카오 사용량 대조. [관리 화면 증빙](evidence/checklist-26-account-quotas.png) |

## 실제 연동과 기획 검증

- 카카오 주소·키워드, 연립다세대 전월세, 건축HUB 표제부는 실제 HTTP 200으로 확인했습니다. 전월세와 건축HUB는 제공자 내부 코드 `000`·`00`을 확인했습니다. 유효·빈 결과·인증 오류를 구분하고 내부 DTO로 정규화했습니다. [실제 API 로그](evidence/phase-01-live.jsonl) · [인증 오류](evidence/phase-01-invalid-auth.jsonl)
- GMS Responses는 실제 HTTP 200, 모델 `gpt-6.1-sol` 일치, Tool 3종 선택과 인자 검증을 확인했습니다. 실제 Agent와 Vue에서 조건 변경, 초안 저장·재조회 및 실행 이벤트 표시를 확인했습니다. 기존 429 이력 뒤 HTTP 200을 실측했으며 저장소 정리 회귀에서는 새 실호출을 하지 않았습니다. [GMS 실행](evidence/phase-01-gms.jsonl) · [실제 시나리오 측정](evidence/day-03-scenarios.json)
- 외부 API 증거 저장 시각은 2026-11-19 17:17:57 KST, GMS 증거 파일 수정 시각은 같은 날 17:44:50 KST입니다. 해당 파일은 최초 Git 기록 `d7f0c4a`(2026-11-20 10:05:34 KST)에 포함됐습니다. 파일 시각과 Git 이력은 기술 검증 자료의 출처를 보여줍니다. 27번 통과는 제출자의 직접 확인을 반영한 결과입니다. 공식 요구사항 PDF는 대외비 로컬 사본으로 검토했습니다. [27번 Git 이력](evidence/checklist-27-planning-records.png) · [제출 파일 검증 화면](evidence/checklist-27-submission-manifest.png)

### 외부 API 이용 조건

| 제공자 | 실제 적용 및 호출 범위 |
|---|---|
| 카카오 로컬 | 카카오맵 ON과 무료 쿼터 표시, 2026-11-20 15:00 KST 일간 주소 17/100,000, 키워드 3/100,000. Tool 요청당 1회. [공식 쿼터](https://developers.kakao.com/docs/ko/getting-started/quota) · [운영 정책](https://developers.kakao.com/terms/ko/site-policies) |
| 연립다세대 전월세 | 개발계정 승인, 2026-11-19~2028-11-19, 해당 기능 일일 10,000건. 지역·계약월당 최대 20페이지·페이지당 100건, 후보가 충분하면 중단. [공식 조건](https://www.data.go.kr/data/15126473/openapi.do) |
| 건축HUB | 개발계정 승인, 같은 적용 기간, 표제부 기능 일일 10,000건. 필지당 첫 페이지 100건. [공식 조건](https://www.data.go.kr/data/15134735/openapi.do) |

공공데이터 두 상세 화면의 누적 호출량은 미확인입니다. 제공자 HTTP 호출에는 자동 재시도나 리다이렉트가 없으며 Agent는 동일 Tool·인자 결과를 실행 중 재사용합니다. 카카오의 공개 쿼터 소진 응답은 HTTP 400·`-10`으로, 현재 공통 HTTP 400 분류에서는 입력 오류와 함께 처리될 수 있습니다. [카카오맵 오류 정책](https://developers.kakao.com/docs/ko/kakaomap/common) · [실제 계정 화면](evidence/checklist-26-account-quotas.png)

## 대표 시나리오 5건

FastAPI·LangGraph·SQLite 및 Logging Agent를 실행했습니다. 아래 5건은 Mock GMS·합성 외부 데이터이며 기대·실제 분기가 일치했습니다. 전체 로그에는 최종 응답, 모든 이벤트, Tool 호출·재계획과 처리 시간이 있습니다. [정제 실행 원본](evidence/day-03-scenarios.json) · [실행 캡처](evidence/checklist-06-agent-scenarios.png)

| 시나리오 | 기대·실제 결과 | Tool / 재계획 / 이벤트 | HTTP 전체 |
|---|---|---:|---:|
| 최초 충족 | SUCCEEDED, 월세 PASS | 3 / 0 / 25 | 150ms |
| 대안 충족 | SUCCEEDED, 월세 FAIL → PASS | 4 / 1 / 40 | 274ms |
| 상한 도달 | EXHAUSTED, 3회 종료 | 4 / 3 / 69 | 445ms |
| Tool 실패 | PARTIAL, 표제부 TIMEOUT과 거래 결과 유지 | 3 / 0 / 25 | 168ms |
| 일반 대화 | SUCCEEDED, Tool 불필요 | 0 / 0 / 7 | 65ms |

별도 실제 Chrome 측정은 신규 계획 **16.46초**, 후속 월세 변경 **7.13초**, 재계획 3회 종료 **22.63초**, 잘못된 링크 입력 안내 **0.37초**였습니다. 대기 UI는 지역·예산·일정과 대안 검토를 안내하고 종료 후 타임라인을 표시합니다. 23번 통과는 실측과 제출자의 직접 확인을 근거로 합니다. [Mock·실제 측정 대조](evidence/checklist-23-measurements.png) · [실제 대기](evidence/checklist-23-live-wait.png) · [상한 응답](evidence/checklist-23-live-result.png) · [오류 화면](evidence/checklist-23-live-error.png)

23·27번 증빙 화면의 최종 판정은 공식 체크리스트와 동일하게 제출자 확인 기준으로 표시합니다.

## 최종 설치·회귀 검증

| 실행 | 결과 |
|---|---|
| 새 Python 3.11.9 가상환경에서 `python -m pip install -r requirements.txt`와 `python -m pip check` | 설치 성공, 의존성 충돌 0건 |
| `python -m pytest -q` | 79개 통과. F3020 규칙·GMS 실패 격리 및 SQLite·Memory·계획·로깅 포함. Starlette의 HTTPX TestClient 지원 중단 예정 경고 1건 |
| `npm.cmd --prefix frontend ci`, `npm.cmd --prefix frontend test`, `npm.cmd --prefix frontend run build` | 재설치 성공, 6개 통과, 프로덕션 빌드 성공 |
| 새 가상환경의 FastAPI·Vue Chrome 실행 | `/api/v1/health` 정상과 Swagger 표시 확인. Mock 시연에서 세션, 채팅, 월세의 세션 내 변경, 재계획 1회, 계획 저장·이름 수정·삭제, SQLite 실행 이벤트 조회 확인 |
| 제출 파일 감사 | 체크리스트 32개 경로와 README·검증 문서 링크 유효. G/I열과 집계 수식 보존. 기존 이미지와 구조화 실행 로그 보존. 환경설정 비밀값 일치 및 금지 경로 0건 |
