# Youth Kitty Planner (청년냥이 플래너) — Phase 4 구현 및 검증

- 작성일: 2026-11-20 KST
- 구현 및 통합 검증: **F3018·F3019 PASS**
- GMS 실제 연결: **BLOCKED — HTTP 429**. Chrome 통합 검증에서는 GMS와 외부 제공자를 합성 응답으로 대체했다. Vue, FastAPI, LangGraph, 세션·계획·로그 SQLite는 실제 실행했다.

## 구현

| 요구사항 | 구현 |
|---|---|
| F3018 | Vue 3·Vue Router의 AI 플래너, 내 계획, 실행 기록 화면. 기존 FastAPI의 세션 발급·Bearer 인증과 채팅, 계획 CRUD, 로그 조회·삭제를 호출 |
| F3019 | 요청 중 로딩 표시. 응답 또는 오류 종료 후 저장 이벤트의 순번대로 단계·Tool 성공/실패·재계획·소요 시간 표시. 호출 제한, 서버 API 키 설정 및 사용자 세션 만료를 구분 |

채팅의 초안에서 계획을 저장하고, 별도 제목 수정 및 명시적 작업 추가·수정·삭제를 사용한다. 일정 충돌은 경고와 함께 저장하며 409에는 최신 계획을 다시 불러오는 동작을 제공한다. 미확정 작업 시간은 NULL, 시간 입력은 한국시간이다. 전월세 자료를 과거 계약으로 표시하며 건물 일치와 현재 매물은 증거가 없으면 UNKNOWN을 유지한다.

토큰은 브라우저 탭 세션 저장소에서만 사용하고 API에는 Bearer 헤더로 보낸다. 만료 시 저장값과 이전 화면 상태를 비우고 명시적인 새 세션 시작을 안내한다. Vite는 동일 출처의 `/api`만 로컬 FastAPI로 프록시하므로 CORS 허용 출처를 넓힐 필요가 없었다. 백엔드 경로·스키마 및 기존 67개 테스트를 유지했다.

## 브라우저 검증

Chrome에서 Vite와 FastAPI Mock 실행을 연결하고 생성한 임시 세션만 사용했다.

| 시나리오 | 결과 |
|---|---|
| 세션 및 채팅 | POST 세션 201, 대화 200. 답변·출처·UNKNOWN·초안 렌더링 |
| 후속 조건 | 월세만 변경 요청 200. 기존 준비 날짜를 유지한 초안을 표시 |
| 계획 CRUD | 초안 저장 201, 목록·상세 조회, 작업 추가·수정·삭제, 계획 삭제 후 빈 목록 |
| 저장 시 중복 | 작업을 10:00–11:00, 10:30–11:30 KST로 설정해 저장과 함께 중복 1건 확인. 다른 작업의 미지정 시간 유지 |
| 409 | 임시 DB에서 열린 계획의 revision을 변경해 실제 PATCH 409를 유발. 안내와 최신 버전 재조회, 이후 작업 수정 가능 확인 |
| 실행 기록 | 채팅 완료 후 서버 이벤트 표시. 실패한 실행의 상태·소요 시간·호출 제한 표시, 세션별 조회·삭제와 빈 상태 확인 |
| GMS 제한 | 합성 RATE_LIMITED가 FastAPI 502로 변환되는 경로에서 전용 UI 안내와 실패 이벤트 표시. 자동 재시도 없음 |
| 서버 API 키 오류 | 합성 AUTH_FAILED에서 키 설정 안내와 실패 이벤트 확인. 사용자 세션은 유지 |
| 세션 만료 | 임시 세션 만료 후 FastAPI의 실제 401, 이전 상태 정리·새 세션 발급 확인 |
| 반응형 | 데스크톱 1278px와 모바일 390px 뷰포트에서 검증. 모바일 채팅·계획·실행 기록에서 가로 넘침 없음 |
| API 계약 | Chrome에서 FastAPI Swagger UI를 열어 세션·채팅·계획·로그 경로와 스키마를 확인하고 화면을 캡처 |

## 실행 결과

| 명령 | 결과 |
|---|---|
| `npm.cmd --prefix frontend test` | 종료 0 · 클라이언트 6개 통과. Bearer, 502/RATE_LIMITED, API 키 오류와 401, 409, 한국시간·NULL |
| `npm.cmd --prefix frontend run build` | 종료 0 · Vue 프로덕션 빌드 |
| `.venv/Scripts/python -m pytest -q --tb=short` | 종료 0 · 기존 백엔드 67개 통과 |
| `.venv/Scripts/python -m scripts.verify_gms_preflight` | 종료 1 · 실제 GMS HTTP 429. 이번 UI 통합 결과는 실제 AI 응답으로 집계하지 않음 |

Git 후보 텍스트 78개에서 실제 환경 키 4종과 일반 토큰 패턴 검출은 0건이었다. `.env`, 프론트엔드 의존성, 빌드 산출물은 Git 제외를 확인했다.

## 실행 및 변경 파일

1. 레포 루트에서 `npm.cmd --prefix frontend ci`와 `.venv/Scripts/python -m pip install -r requirements-dev.txt`로 의존성을 준비한다.
2. 첫 터미널에서 `.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`을 실행한다.
3. 두 번째 터미널에서 `npm.cmd --prefix frontend run dev`를 실행하고 브라우저에서 `http://127.0.0.1:5173`에 접속한다. 운영 정적 배포에서는 이력 경로의 SPA fallback과 동일 출처 `/api` 라우팅을 사용한다.
4. Mock 검증 시 두 번째 단계 대신 `.venv/Scripts/python -m uvicorn ui_preview:create_preview --factory --app-dir tests/integration --host 127.0.0.1 --port 8000`을 사용한다. 임시 SQLite와 합성 제공자만 사용한다. `테스트: 호출 제한` 및 `테스트: 인증 설정`으로 오류를 재현할 수 있다.

신규 경로는 `frontend/`의 Vue 화면·API 모듈·스타일·빌드 설정·락파일·클라이언트 테스트, 브라우저용 `tests/integration/ui_preview.py`, 시작 안내 `README.md`, 이 보고서다. 확정 백엔드, Phase 1~3 보고서, 기존 테스트는 직접 재사용했다. SSE와 선택 심화 기능은 범위에 포함하지 않았다.

## GMS 독립 장애 진단

| 항목 | 결과 |
|---|---|
| 실행 명령 | `.venv/Scripts/python -m scripts.verify_gms_preflight --single-request` |
| 호출 시각 | 2026-11-20 09:53:28 KST |
| 대상·횟수 | 기존 `.env`의 SSAFY GMS Responses API와 `gpt-6.1-sol` · 텍스트 1회, 재시도 0회 |
| HTTP 및 시간 | **429**, 전체 1,219 ms, 종료 코드 1 |
| 정상 완료 | 비정상. 완료 상태와 기대 텍스트를 확인하지 못했다 |
| 모델 일치 | UNKNOWN. 응답의 모델 식별값 미확인 |
| 제공자 오류 코드·유형 | 안전하게 추출 가능한 구조화된 코드·유형 미확인 |
| `Retry-After` | 헤더 없음, 값 없음 |

이 요청이 HTTP 429로 거부된 점은 확인했다. 계정·키의 쿼터 초과, 요청 빈도 제한, 모델별 제한 중 어느 조건에 해당하는지 구분할 응답 근거가 없었다. 서버 혼잡 또는 서비스 장애 여부도 확인되지 않았다. 공개 검색에서 이 시각의 공식 GMS 상태 공지를 확인하지 못해 **GMS 전체 장애는 UNKNOWN**으로 기록한다.

추가 확인에는 SSAFY 운영 공지와 해당 계정의 잔여 쿼터·요청 빈도·모델별 한도 정보가 필요하다. 실제 GMS 응답이 필요한 전체 통합 검증은 **BLOCKED**다. 이번 작업은 GMS 단일 요청만 실호출했다. 기존 GMS 단위 테스트 6개 및 합성 429로 단일 호출·안전한 헤더 처리 검증을 통과했다.

## 최종 통합 검증 및 시연 준비

검증일 2026-11-20 KST. 최종 작업에서는 **GMS 실호출 0회**였다. 위 독립 진단의 HTTP 429는 그대로 기록하고, 이후 회복 여부는 미확인이다.

| 구분 | 실행 결과 |
|---|---|
| 구동 | 기존 Vue 명령에서 Vite 5173 및 페이지 HTTP 200. 실제 설정의 FastAPI 앱은 검증 포트 8001에서 시작했고 health 200. 해당 앱에 GMS 요청을 보내지 않았다. |
| 통합 및 시연 | 실제 Vue·Vite 프록시·FastAPI·LangGraph·SQLite에 Mock GMS와 Mock 데이터 제공자를 연결했다. 세션 201, 대화 200/PARTIAL, 완료 로그 40건 순서 일치, 월세 제약 FAIL → 재계획 1회 → PASS, 표제부 실패 후 건물 UNKNOWN과 거래 보존을 확인했다. 월세만 변경한 후속 요청은 SUCCEEDED이며 보증금·출근일·지역 조건이 유지됐다. |
| 계획·로그·예외 | 계획 생성 201·재조회·수정·삭제, 작업의 중복 경고 1건 및 미정 시간 유지, 오래된 revision 409, 로그 목록·상세·삭제, 합성 RATE_LIMITED의 HTTP 502, 인증 없는 요청 401을 확인했다. Chrome에서 세션 만료 401과 새 세션, 계획 수정·삭제 및 실패 타임라인을 재검증했다. |
| 화면 | Chrome 1278px 데스크톱, 390px 모바일에서 확인했다. 모바일의 채팅·계획·기록 세 화면에 가로 넘침이 없었다. |
| 독립 실제 데이터 API | `.venv/Scripts/python -m scripts.verify_external_apis --match` 종료 0. 카카오 주소·키워드 HTTP 200, 전월세 HTTP 200/000, 표제부 HTTP 200/00. 건물 연결 1건과 UNKNOWN 2건을 확인했다. 이 호출은 GMS 및 Mock 브라우저 검증과 별개다. |
| 테스트·빌드 | 백엔드 pytest 67개, 프론트엔드 Node 테스트 6개 모두 통과. `npm.cmd --prefix frontend run build` 종료 0. |

### NF3001~NF3007 최종 판정

| 요구사항 | 상태 | 근거 |
|---|---|---|
| NF3001 키 관리 | PASS | 환경변수 설정을 사용하며 `.env`, SQLite 및 원본 API 자료는 커밋 후보에서 제외했다. Git 인덱스의 내용도 실제 키·인코딩 변형과 토큰 패턴으로 검사했다. |
| NF3002 화면 비노출 | PASS | Chrome의 401·호출 제한 안내와 클라이언트 409·인증 오류 테스트에서 원본 오류 및 자격증명 미노출을 확인했다. |
| NF3003 장애 격리 | PASS | Mock 표제부 실패 시 HTTP 200/PARTIAL, 거래 결과 유지 및 Tool 실패 이벤트를 확인했다. 기존 Logging Agent 장애 회귀 테스트도 통과했다. |
| NF3004 재계획 상한 | PASS | 최종 시연에서 재계획 1회 및 이벤트를 확인했다. 기존 모든 대안 실패·중복 전략 테스트에서 최대 3회 종료를 확인했다. |
| NF3005 응답 시간 | BLOCKED | Vite 프록시 경유 Mock 요청 단건 측정은 재계획 포함 계획 243ms, 후속 변경 168ms, 호출 제한 응답 58ms였다. 현재 실제 GMS를 포함한 대표 서비스 응답 시간은 미검증이다. |
| NF3006 모듈 분리 | PASS | Vue/Vite와 FastAPI를 별도 포트에서 실행했다. API에서 연결하며 백엔드의 Agent·Tool·저장 모듈을 분리했다. |
| NF3007 이용 조건 | BLOCKED | 공개 출처와 이용 조건은 이전 보고서에 기록되어 있고 현재 인증 호출은 정상이다. 프로젝트별 적용 쿼터와 승인 상태는 계정 관리 화면의 확인이 남았다. |

시연 재현 순서는 레포의 `README.md`에 추가했다. 초기 커밋 후보 78개는 코드·설계·비식별 증거와 문서다. 스테이징한 파일 내용에서 실제 환경 키 4종과 일반 토큰 패턴 검출은 0건이었다. 대외비 표시가 있는 공식 PDF는 로컬에 보존하며 Git 제외를 적용했다. 원격 전송은 수행하지 않는다.

### 제출 상태

- 필수 기능 **F3001~F3019 구현 완료**. 기존 코드·테스트와 위의 Mock 시연 검증을 제출 기준으로 삼는다. 실제 GMS 연동 성공 여부는 별도 항목이다.
- **NF3005·NF3007은 미검증(BLOCKED)**. 실제 GMS를 포함한 대표 응답 시간과 프로젝트 계정별 API 승인·적용 한도가 확인되지 않았다.
- GMS의 마지막 실제 응답은 **HTTP 429**였으며 회복 여부는 미확인이다. 제출 직전 점검에서 GMS를 호출하지 않았다.
- README의 일반 서버 진입점과 Mock 팩터리 명령, Vite 포트 및 API 프록시가 기존 실행 설정과 일치한다.
- 초기 로컬 커밋은 `d7f0c4ad5589d160e6009204d18e9a761c7f4a51`이다. 제출 상태 기록만 이 보고서의 작업 트리에 반영했다.

## 3일 차 구현 및 최종 검증

검증일 2026-11-20 KST. 필수 F3001~F3019에 F3020을 추가했다. 기존 REST 경로, DTO와 SQLite 스키마를 사용한다. F3021~F3023은 미착수다.

### F3020 실행 이상 징후

- Logging Agent가 원본 이벤트를 SQLite에 순서대로 저장한다. 판정기는 종료 이벤트를 발행하기 전에 같은 세션·실행의 저장 이벤트를 조회한다. 이벤트 수집과 저장에서는 LLM 호출이 0회다.
- 같은 실행에서 같은 인자로 실제 호출한 Tool의 중복, 재계획 상한 3회 초과, Workflow에 없는 Tool, 계획 단계와 Tool 실행 내역의 불일치를 규칙으로 검출한다. 명시적으로 건너뛴 단계와 캐시 재사용을 근거에 포함한다. 정상 경로의 Tool 실패나 재계획 상한 도달은 각각 계획상 허용된 결과다.
- Tool 인자의 Pydantic 정규화 값에서 실행마다 다른 키로 지문을 계산한다. 원본 인자와 지문 키는 저장하지 않는다. 이벤트 누락 또는 근거 부족에는 `UNKNOWN`을 반환한다. 판정과 근거 sequence를 기존 종료 이벤트의 `payload.anomaly`에 남긴다. Main Agent는 이상 실행에 기존 응답의 경고를 추가한다.
- `ANOMALOUS`에만 기존 GMS Responses 연결로 진단을 1회 요청한다. 모델에는 규칙 코드만 전달하고, 허용된 원인 분류만 저장한다. Mock HTTP 429에서 `INCOMPLETE/RATE_LIMITED`를 기록하면서 대화·초안·로그 조회가 유지됐다. `NORMAL`과 `UNKNOWN`의 진단 호출은 0회였다. **F3020은 Mock 검증 PASS, 실제 GMS 원인 진단은 BLOCKED**다.

### 대표 요청 검증

FastAPI TestClient, 실제 LangGraph, Logging Agent, 임시 SQLite를 연결했다. 이 실행의 GMS와 외부 데이터 API는 Mock이다. 아래 5건 모두 HTTP 200이고 실행 순서, 세션 로그 일치, 판정 `NORMAL` 및 진단 미호출을 확인했다. [대표 요청·최종 응답·단계별 전체 실행 이벤트](evidence/day-03-scenarios.json)

| 시나리오 | 기대 결과 | 실제 결과 | 차이 |
|---|---|---|---|
| 최초 요청에서 제약 충족 | 월세 PASS, 재계획 없음 | SUCCEEDED, Tool 3회, 재계획 0회, 이벤트 25개 | 없음 |
| 대안으로 제약 충족 | 월세 FAIL 후 승인 대안 PASS | SUCCEEDED, Tool 4회, 재계획 1회, 이벤트 40개 | 없음 |
| 재계획 상한 도달 | 모든 월세 FAIL, 상한에서 종료 | EXHAUSTED, Tool 4회, 재계획 3회, 이벤트 69개 | 없음 |
| 건축물대장 Tool 실패 | 임대차 근거를 유지하고 건물 확인 불가 표시 | PARTIAL, Tool 3회 중 TIMEOUT 1회, 건물 UNKNOWN, 이벤트 25개 | 없음 |
| Tool 불필요 | 일반 응답, Tool 호출 없음 | SUCCEEDED, Tool 0회, 재계획 0회, 이벤트 7개 | 없음 |

Chrome에서는 README의 Mock 시연 요청으로 재계획 1회, 월세 미충족에서 충족으로 변경, 건축물대장 Tool 실패와 전체 이벤트 40개의 Vue 화면 표시를 확인했다. 현재 매물과 건물 일치 상태는 UNKNOWN으로 표시했다. [대화 화면](evidence/day-03-mock-chat.png) · [실행 기록 화면](evidence/day-03-mock-timeline.png)

### 테스트와 제출 자료

| 실행 명령 | 결과 |
|---|---|
| `.venv/Scripts/python -m pytest -q tests/integration/test_api.py -k "anomaly_assessment or tool_argument_fingerprints"` | 신규 10개 통과, 종료 0 |
| `.venv/Scripts/python -m pytest -q` | 백엔드 77개 통과, 종료 0. 기존 67개 포함 |
| `npm.cmd --prefix frontend test` | 기존 6개 통과, 종료 0 |
| `npm.cmd --prefix frontend run build` | 프로덕션 빌드 성공, 종료 0 |

- 소스코드와 [README](../README.md), [요구사항 추적·Agent 설계·API 계약](../YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md), [Tool 정의서](evidence/phase-01-tool-specs.json)를 제출 자료로 정리했다. 로컬 `/openapi.json`의 HTTP 200과 기존 경로 8개의 메서드 구성을 확인했다.
- 실행 증거는 합성 요청을 사용했다. 제출 로그에서 세션·실행·이벤트 식별자는 별칭으로 대체했고 내부 증거 연결 값은 제외했다. 신규 스크린샷은 임시 Chrome 프로필과 로컬 Mock 데이터로 촬영했다. 변경·신규 파일 14개에서 실제 환경변수의 비밀값이 검출되지 않았다.
- 공식 SSAFY 요구사항 원본은 대외비 표시가 있어 제공받은 로컬 사본을 사용한다. 오후 공식 셀프 체크리스트는 프로젝트와 제공된 첨부에서 확인되지 않아 점검을 보류한다.
- Day 3 실제 GMS 및 외부 데이터 API 호출은 각각 0회다. 외부 데이터 API 실제 호출 근거는 위의 Phase 4 통합 검증과 [Phase 1 실행 증거](evidence/phase-01-live.jsonl)에 있다. GMS의 마지막 실제 응답은 HTTP 429이며 회복 여부는 미확인이다. NF3005·NF3007은 BLOCKED를 유지한다.

## 3일 차 제출 마무리 및 실제 GMS 재검증

기존 `.env`와 `gpt-6.1-sol`을 사용했다. 2026-11-20 10:24:04 KST에 `.venv/Scripts/python -m scripts.verify_gms_preflight --single-request`로 연결을 한 번 확인했다. 초기 HTTP 429 기록과 대표 요청 5건의 Mock 증거를 보존한다.

| 실제 검증 항목 | 상태 | 실행 근거 |
|---|---|---|
| GMS 연결 | PASS | HTTP 200, 2,031 ms, `completed`, 모델 일치, 기대 텍스트 일치, 오류 코드·유형 없음, `Retry-After` 없음, 종료 0. |
| Tool Calling | PASS | 기존 preflight 샘플의 장소·전월세·표제부 요청을 각 1회 실행했다. 각각 HTTP 200이고 `search_location` 2,703 ms, `search_rental_transactions` 3,391 ms, `get_building_detail` 3,203 ms였다. 반환된 Tool 이름, Pydantic 인자 검증, 기대 인자 대조가 3건 모두 통과했다. 이 단계에서는 외부 데이터 Tool을 실행하지 않았다. |
| Agent E2E | PASS | 실제 FastAPI·LangGraph·임시 SQLite에서 세션 201, 채팅 200 및 `CREATE_PLAN/PARTIAL`, 실제 GMS 의도 분석·Tool 계획, 실제 전월세·카카오·건축HUB HTTP 200 및 Tool 3건 성공, 일정·보증금·월세 제약 PASS를 확인했다. 건물 일치와 현재 매물 여부는 UNKNOWN으로 유지했다. 작업 2개 초안, 계획 저장 201·동일 계획 재조회 200, 실행 이벤트 25건과 로그 200을 확인했다. |
| Vue 실제 AI 통합 | PASS | Chrome에서 기존 Vue·Vite 프록시로 채팅, 과거 거래 안내, 현재 매물 UNKNOWN, 계획 초안 저장·재조회 및 실행 타임라인 25개를 확인했다. 해당 구간에서 GMS와 외부 데이터를 실제 호출했다. |
| F3020 GMS 원인 진단 | PASS | 합성 Workflow에 계획 외 Tool을 기록한 사례에서 규칙이 이상을 감지했다. 실제 GMS 1회가 HTTP 200(3,593 ms)을 반환했고 기존 허용 분류 `WORKFLOW_DISPATCH`로 완료됐다. 합성 정상·증거 부족 사례는 `NORMAL`·`UNKNOWN`, 진단 호출 각 0회였다. 이 검증의 의도 분석과 외부 데이터는 Mock이다. |
| NF3005 실제 응답 시간 | BLOCKED | 대표 요청 2건의 서버 실행 시간은 11,328 ms와 13,641 ms였다. 두 번째 요청의 브라우저 응답 표시까지 13,707 ms가 걸렸다. 한 요청 유형과 한 환경에서 측정했으며, 다양한 대표 요청과 실제 이용자의 대기 적합성은 확인이 필요하다. |
| NF3007 외부 API 이용 조건 | BLOCKED | 실제 인증 호출 성공을 확인했다. 계정에 적용된 승인 범위와 쿼터는 확인 대기다. |

첫 대표 요청에서 서버 실행을 확인했으나 브라우저 측정기가 UI 응답을 수집하지 못했다. 브라우저 네트워크 관측 방식으로 바꾼 뒤 사용자가 보는 흐름을 요청 1건으로 확인했다. 이번 재검증의 실제 GMS 호출은 연결 1회, Tool Calling 3회, 대표 요청 2건의 의도·계획 4회, F3020 진단 1회로 총 9회다. 대표 요청의 실제 외부 데이터 API 호출은 전월세·카카오·건축HUB 각 2회다. 재검증 중 HTTP 429 및 자동 재시도는 없었다. 계정·인증·원본 응답은 보고서에 기록하지 않았다.

백엔드 테스트 77개와 프론트엔드 테스트 6개가 모두 통과했고 Vue 프로덕션 빌드도 성공했다. 세 실행 명령의 종료 코드는 모두 0이다.

| 제출 자료 | 확인 결과 |
|---|---|
| 요구사항 정의 | [F3001~F3019 및 NF3001~NF3007 요구사항 추적](../YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md). 공식 SSAFY 원본은 로컬에 존재하며 대외비 표시로 저장소에서 제외한다. |
| Agent 설계 및 Tool 정의 | [Agent 설계와 재계획·로그 명세](../YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md) · [Tool 3종 입출력 정의](evidence/phase-01-tool-specs.json) |
| API 명세 | [REST 경로 및 DTO](../YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md). 기존 FastAPI가 로컬 `/docs`와 `/openapi.json`에서 제공한다. |
| 구현 및 실행 안내 | 기존 백엔드·Vue 소스와 [README](../README.md) |
| 검증 이력과 제출 증거 | [대표 요청 5건 전체 로그](evidence/day-03-scenarios.json) · Mock 화면 [대화](evidence/day-03-mock-chat.png) · [실행 기록](evidence/day-03-mock-timeline.png). 이 절에 실제 연동 수치와 판정을 보존했다. |
| SSAFY 오후 공식 셀프 체크리스트 | 확인 대기. 저장소와 제공된 첨부에서 해당 문서를 확인하지 못했다. |

Day 3 커밋 대상은 변경·신규 파일 14개다. Git 인덱스 전체 82개 파일의 경로와 내용을 검사했다. 실제 환경변수 비밀값과 인코딩 변형, 토큰 패턴 및 제외 대상 경로가 검출되지 않았다. 새 증거에는 Mock 스크린샷과 비식별 로그를 포함했고 실제 요청의 원본 응답은 추가하지 않았다.
