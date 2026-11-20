# Youth Kitty Planner (YKP) — Phase 1 최종 승인 전 검토

- 검토일: 2026-11-19 KST
- 상태: **Phase 2 진입 승인 대기 (BLOCKED)**. F3001~F3004 및 GMS 연결·Tool 선택 사전검증은 PASS.
- 합격 기준: PASS는 직접 실행 증거가 있는 항목, BLOCKED는 필요한 증거에 접근할 수 없는 항목, NOT_STARTED는 해당 기능을 아직 구현·검증하지 않은 항목이다.

## 0. Phase 2 직전 재점검

- **회귀 테스트:** `.venv/Scripts/python -m pytest -q` 종료 코드 0, 기존 **37개 통과**. 설정·테스트·애플리케이션 코드와 확정 스키마는 이번 점검에서 수정하지 않았다.
- **실행 증거:** 저장된 외부 API 기록의 정상 인증 HTTP 200 및 국토부 내부 성공 코드 `000`·`00`, 인증 거부 4건, 건물 일치 1건·UNKNOWN 2건을 재확인했다. GMS 실제 HTTP 200 5건, Tool 각각 1회 선택과 일반 요청의 선택 0건, Registry 명세도 보고서와 일치했다. 이번 재점검에서는 저장 증거를 읽었다. [외부 API](evidence/phase-01-live.jsonl) · [인증 거부](evidence/phase-01-invalid-auth.jsonl) · [GMS](evidence/phase-01-gms.jsonl)
- **비밀정보:** Git 제외 규칙은 `.env`, `.env.local`, 가상환경, 런타임 DB, 원본 실행 증거 경로에 적용된다. 후보 텍스트 32개에 실제 키 4종 및 인코딩 변형과 일반 토큰 패턴을 검사해 검출 0건을 확인했다. [검사 절차](evidence/phase-01-security.md)

### 초기 커밋 절차 점검

`main`의 첫 커밋이 없고 Git 인덱스가 비어 있어 추적 파일은 0개다. 구현은 작업 트리의 미추적 파일로 존재한다. 허용 경로의 `git add --dry-run`을 임시 인덱스에서 실행해 32개 후보를 확인했다. 실제 인덱스는 읽기 전용이어서 첫 dry-run이 잠금 파일 생성 단계에서 실패했다. 임시 인덱스 실행은 종료 코드 0이었다. 실제 스테이징·커밋·푸시는 수행하지 않았다.

1. 로컬 초기 커밋을 할 때 `git add -- .gitignore .env.example requirements.txt requirements-dev.txt YKP_codex_handoff_v1 backend scripts tests reports/phase-01.md reports/evidence`처럼 검토한 경로만 지정한다. 대외비 표시가 있는 공식 원본 PDF는 배포 권한 확인 전 커밋 후보에서 제외한다.
2. `git diff --cached --name-only`로 목록을 확인하고, 스테이징된 파일 내용에서 실제 키·토큰과 민감정보를 비출력 방식으로 검사한다. `git diff --cached --check`와 기존 테스트를 통과하면 로컬에서 `git commit -m "Initialize YKP Phase 1 baseline"`을 실행한다.

### 카카오 오류 분류 최소 수정안

현재 공통 `fetch()`는 HTTP 400을 모두 `INVALID_ARGUMENT`로 분류한다. 카카오 로컬에서만 공통 함수에 선택적으로 제공자 쿼터 코드를 지정하고, HTTP 400의 JSON `code`가 정수 `-10`인 경우 기존 `RATE_LIMITED`로 반환하는 방안을 제안한다. 다른 400과 JSON 파싱 실패는 기존 `INVALID_ARGUMENT`로 처리한다. 원문 오류 메시지·응답은 전달하지 않는다. Mock에 `400/-10`, 일반 400, 비JSON 400을 추가해 구분과 정보 비노출을 검증한다. 수정안은 이번에 적용하지 않았다. [카카오맵 쿼터 정책](https://developers.kakao.com/docs/ko/kakaomap/common) · [REST 오류 응답 형식](https://developers.kakao.com/docs/ko/rest-api/reference)

**사용자 확인 항목:** 카카오 앱의 활성화·적용 쿼터, 전월세·건축HUB 각각의 실제 활용 승인 상태·할당량·적용 기간, SSAFY 팀 공식 1일 차 날짜와 16시 기준 충족 근거가 필요하다. 공개 신청 가능량과 프로젝트 적용량을 구분하며 비밀값은 확인 자료에서 제외한다. Phase 2는 미착수다.

**파일 변경:** 기존 `reports/phase-01-final-review.md`를 표준 경로 `reports/phase-01.md`로 옮겨 직접 갱신했다. 이전 경로에는 별도 보고서를 두지 않았으며 신규 산출물은 없다.

## 1. F3001~F3004 최종 판단

| 요구사항 | 상태 | 실행 증거 |
|---|---|---|
| F3001 Tool 등록과 계약 | PASS | 저장된 Tool 명세가 현재 Registry 출력과 일치했다. 세 명세를 Responses의 평탄한 function 형식으로 변환해 GMS가 세 가지를 각각 선택했다. 기존 Pydantic DTO로 인자와 결과의 검증·왕복을 확인했다. [등록 명세](evidence/phase-01-tool-specs.json) · [GMS 실행](evidence/phase-01-gms.jsonl) · [테스트](evidence/phase-01-final-tests.txt) |
| F3002 과거 실거래 후보 | PASS | 유효 인증 HTTP 200, 내부 코드 000. 첫 페이지에서 후보 3건 반환. 직전 완료월, 빈 결과, 페이지 1·2, 공식 만원 단위와 원화 정수 DTO 확인. [인증 HTTP 증거](evidence/phase-01-live.jsonl) |
| F3003 건물 상세 | PASS | 유효 인증 HTTP 200, 내부 코드 00. 후보 ID 전파 3건, 건물 일치 1건, 이름 부재 UNKNOWN 2건. 다건과 빈 필지 검증도 별도로 존재한다. [인증 HTTP 증거](evidence/phase-01-live.jsonl) |
| F3004 주소·키워드 | PASS | 두 유효 조회 HTTP 200, 주소·좌표·법정/행정동, 키워드 장소 링크 확인. 빈 주소는 HTTP 200/NO_RESULT. 요청 오류 400과 인증 실패 401 구분. [인증 HTTP 증거](evidence/phase-01-live.jsonl) · [인증 실패 증거](evidence/phase-01-invalid-auth.jsonl) |

## 2. NF3001~NF3007

| 요구사항 | 상태 | 근거 또는 남은 검증 |
|---|---|---|
| NF3001 키 환경변수 관리 | PASS | `.env` 제외 확인. 외부 API 3종과 GMS 키를 환경설정에서 사용했고, 명세·보고서·로그·테스트 후보 텍스트에서 실제 키 또는 인코딩 변형 0건을 확인했다. [보안 절차](evidence/phase-01-security.md) |
| NF3002 화면 비노출 | NOT_STARTED | Tool 오류와 출력의 비노출 테스트 통과. 화면은 미구현. |
| NF3003 Tool 실패 격리 | NOT_STARTED | 실패 DTO로 변환하고 잘못된 GMS 인자를 로컬 차단한 증거가 있다. 전체 서비스가 이어지는지 확인할 Agent 실행은 미구현. |
| NF3004 재계획 상한 | NOT_STARTED | 재계획 실행 미구현. |
| NF3005 대표 요청 처리 시간 | NOT_STARTED | 실제 API 및 GMS의 개별 호출 시간은 기록했다. 전체 플래너 시나리오의 시간은 측정 대상이 미구현. |
| NF3006 구조 분리 | NOT_STARTED | Registry·Executor·Provider와 DTO는 구분되어 있다. Agent·백엔드·프론트엔드 전체 경계는 후속 Phase에서 검증. |
| NF3007 API 이용 조건 | BLOCKED | 실제 키의 호출 권한과 공개 이용 조건은 확인. 프로젝트별 승인 유형과 적용 쿼터는 계정 관리 화면에서 확인해야 한다. |

## 3. 기존 HTTP·Mock 증거 재검토

`phase-01-live.jsonl`의 인증 정상 결과와 `phase-01-invalid-auth.jsonl`의 가짜 키 실요청을 분리해 확인했다. 기존 pytest 출력과 이번 테스트 결과는 Mock·로컬 검증 증거로만 사용했다. 정상 카카오 주소·키워드는 HTTP 200이며 카카오는 공공데이터포털 형식의 내부 성공 코드를 제공하지 않는다. 전월세는 HTTP 200/XML/000, 건축HUB는 HTTP 200/JSON/00이다. 가짜 인증에서 카카오 두 건은 HTTP 401, 국토부 두 건은 HTTP 403/30이었다.

실제 후보 3건은 모두 표제부 요청과 후보 ID 전파가 기록되어 있다. 집계는 MATCHED_BUILDING 1, AMBIGUOUS 0, NOT_FOUND 0, UNKNOWN 2, 제공자 오류 0이다. UNKNOWN 2건은 동일 필지와 단일 표제부까지 확인했으나 표제부 건물명이 비어 있었다. 응답의 정규화 타입, 검사 목적, HTTP·내부 코드, 시행 시간과 구조 증거는 기존 보고서와 일치했다. 이번 최종 검토는 해당 API 기록을 직접 재판독했고, GMS는 신규 실호출을 실행했다. [HTTP 검증 요약](evidence/phase-01-http.md) · [정상·빈·오류 JSONL](evidence/phase-01-live.jsonl) · [가짜 인증 JSONL](evidence/phase-01-invalid-auth.jsonl)

`phase-01-tool-specs.json`은 현재 `agent_tool_specs()`와 구조적 동일성을 확인했다. Phase 1 실제 실행은 `execute_tool`의 입력 `model_validate`, 등록된 출력 Pydantic 모델과 공통 결과를 경유한다. 정상·실패 DTO의 JSON 왕복과 후보 ID 전파는 별도 테스트로 확인했다. 기존 31개를 다시 실행했고 전부 통과했다.

## 4. SSAFY GMS LLM 및 Tool Calling Preflight

기존 `GMS_KEY`, `GMS_URL`, `GMS_MODEL`을 사용했다. 설정된 SSAFY 공식 HTTPS 호스트의 `/gmsapi/api.openai.com/v1/responses`에 POST했다. 공개 GMS 포털 루트와 문서 후보 경로는 본문이 페이지 없음이어서 GMS 전용 매뉴얼과 모델 카탈로그는 직접 열람하지 못했다. 공식 OpenAI Responses 계약을 사용했고, GMS에서 설정 모델과 응답 `model` 값이 동일한지 비교하여 `gpt-6.1-sol`의 지원을 실측했다. 모델 목록 전체나 다른 환경의 지원까지 검증한 범위는 아니다. [GMS 포털](https://gms.ssafy.io/) · [Responses API 공식 명세](https://developers.openai.com/api/reference/resources/responses/methods/create) · [함수 호출 공식 가이드](https://developers.openai.com/api/docs/guides/function-calling)

요청은 Responses의 `model`·`input`을 사용하고 각 함수의 `type/name/description/parameters`를 `tools`의 동일 레벨에 배치했다. 응답은 `output[]`의 `message/output_text`, `function_call`을 검사했다. Chat Completions의 `choices` 응답은 로컬 검증에서 거절했다. `tool_choice=auto`와 기존 선택 필드를 보존하는 `strict=false`를 사용했다. 모델 인자는 Registry에 등록된 이름과 Pydantic `model_validate_json`을 통과해야 한다. 제안된 Tool은 이 Preflight에서 실행하지 않았다.

| 순서 / 구분 | 실측 결과 | 시간 |
|---|---|---|
| 1. Tool 없는 GMS 연결 | HTTP 200, completed, 텍스트 표식 일치, 모델 ID 일치 | 2,203 ms |
| 2. 주소·장소 요청 | HTTP 200, `search_location`, Pydantic VALID 및 예상 인자 일치 | 2,406 ms |
| 3. 과거 전월세 요청 | HTTP 200, `search_rental_transactions`, Pydantic VALID 및 예상 인자 일치 | 2,094 ms |
| 4. 합성 후보 표제부 요청 | HTTP 200, `get_building_detail`, Pydantic VALID 및 예상 인자 일치 | 2,391 ms |
| 5. 일반 인사 | HTTP 200, 완료된 텍스트, Tool 선택 0건 | 2,484 ms |
| 로컬 합성 Tool 응답 | 미등록 이름, 잘못된 enum, 깨진 JSON 및 문자열이 아닌 인자 각각 차단 | pytest |

LLM의 응답 원문, 함수 인자 값, 키 및 인증 헤더 값은 증거에 저장하지 않았다. 실호출과 로컬 합성 입력 검증을 분리했다. [GMS 증거](evidence/phase-01-gms.jsonl) · [테스트 결과](evidence/phase-01-final-tests.txt)

## 5. 이용 조건과 계정 관리 확인 항목

| 제공자 | 확인된 호출 권한 및 공식 공개 조건 | 계정에서 확인할 항목 |
|---|---|---|
| 카카오 로컬 | 현재 키로 주소·키워드 호출 권한 확인. 공개 기본 일간 각 100,000건. 무료 쿼터는 계정 기준 첫 활성화 앱 등 정책 조건 적용. [쿼터](https://developers.kakao.com/docs/ko/getting-started/quota) · [카카오맵 이용 정책](https://developers.kakao.com/docs/ko/kakaomap/common) | 앱 관리에서 카카오맵 활성화 여부, 적용된 무료·유료 유형, 주소·키워드별 일간 한도 및 월간 한도 |
| 국토교통부 전월세 | 현재 키 호출 권한 확인. 공개 개발계정 신청 가능량 10,000, 개발·운영 자동승인, 무료·이용허락범위 제한 없음. [데이터셋 및 이용 조건](https://www.data.go.kr/data/15126473/openapi.do) | 포털 활용 신청 상세에서 해당 API의 승인 상태, 개발/운영 구분, 적용 한도 및 기간 |
| 국토교통부 건축HUB | 현재 키의 표제부 호출 권한 확인. 공개 개발계정 신청 가능량 10,000, 개발·운영 자동승인, 무료·이용허락범위 제한 없음. [데이터셋 및 이용 조건](https://www.data.go.kr/data/15134735/openapi.do) | 별도 건축HUB 서비스 활용 신청의 승인 상태, 개발/운영 구분, 적용 한도 및 기간 |

공개 신청량은 해당 계정에 실제 적용된 한도의 증거로 사용하지 않았다. 관리 화면 증거에는 승인 상태·유형·할당량·기간만 필요하다. 인증키·앱 식별번호·계정 개인정보는 확인 자료에서 제외한다. [공공데이터포털 이용 정책](https://www.data.go.kr/ugs/selectPortalPolicyView.do)

## 6. 코드·스키마 준수와 위험

| 항목 | 관찰 및 영향 | 검토·승인 |
|---|---|---|
| 변경 범위 | 추가는 `scripts/verify_gms_preflight.py`, `tests/unit/test_gms_preflight.py`, 최종 보고서·실행 증거다. 공식 PDF §2.7의 연결·Tool 선택 확인을 독립 실행했다. 기존 Tool Registry, Executor, Provider, 정규화·매칭 및 설계의 Agent State·Tool DTO·DB·REST 경로는 유지했다. | Preflight 자체로 제품용 GMS 클라이언트나 Main Agent를 승인하지 않음 |
| 후보 건수 제한 | 실거래 후보는 요청 한도까지 반환한다. 적합 후보가 뒤쪽에 있거나 요청 한도 밖이면 전수 탐색으로 해석할 수 없다. 자료는 과거 신고 거래이며 현재 임대 가능성은 UNKNOWN이다. | 기본 후보 수나 정렬, 전수 보장 또는 응답 계약을 변경할 경우 승인 필요 |
| 페이지네이션과 DATA_INCOMPLETE | 두 페이지 실측은 서로 다른 행과 동일 총건수를 확인했다. 실거래 조회는 후보 한도를 넘겨 진행하지 않는다. 20페이지 내에 요청 반환을 완결할 수 없거나 페이지 사이 `totalCount`가 바뀌면 DATA_INCOMPLETE가 발생할 수 있다. 표제부는 다건이면 AMBIGUOUS를 유지한다. | 상한 변경·부분 결과 제공 계약은 별도 검토 |
| 건물명 누락 | 필지 전체가 일치해도 이름이 없던 2건은 UNKNOWN. 소표본이며 다른 지역·월에 일반화할 수 없다. | 기존 잠정 선택 인자 `building_name` 확정과 매칭 기준 완화는 검토자 승인 필요 |
| 국토부 코드 04·05 | 04 `HTTP_ERROR`는 SERVICE_UNAVAILABLE, 05 `SERVICETIMEOUT_ERROR`는 TIMEOUT. 04는 HTTP 200 실제 관찰, 05는 공식 오류표 및 Mock으로 확인했다. 카카오 공식 정책의 쿼터 소진은 HTTP 400과 코드 -10일 수 있다. 기존 공통 HTTP 400 매핑은 INVALID_ARGUMENT이므로 실제 운영 중엔 쿼터 소진과 입력 오류가 혼동될 수 있다. | 카카오 제공자 오류 세분화는 후속 승인 범위에서 검토. 쿼터 소진을 실유도하지 않음. [국토부 오류표](https://www.data.go.kr/data/15126473/openapi.do) · [카카오맵 정책](https://developers.kakao.com/docs/ko/kakaomap/common) |
| XML → JSON | 전월세 공급자 공식 형식은 XML. 내부 계약에서 검증된 JSON DTO로 바꿔 전달한다. 카카오·건축HUB는 JSON 실측. | 공식 PDF JSON 요구를 내부 정규화로 충족한다고 볼지 검토자 확인 필요 |
| GMS 제품 연동 | 팀 설정 모델이 Responses Tool Calling을 지원함을 확인했다. Preflight 변환은 로컬 Registry 원형을 재사용한다. | Phase 2 승인 후에만 제품용 GMS Responses 어댑터와 모델 설정 계약 검토 |
| Git 추적 0개 | `main`에서 `git rev-list --all --count`는 0, `git ls-files` 결과는 비어 있다. 구현은 untracked 작업 트리에 존재한다. 인덱스에 올린 파일이나 이 레포에서 확인 가능한 커밋이 없어 현재 추적 수가 0이다. 원격 커밋 존재 여부까지 판단하지 않는다. | Git 인덱스·브랜치·원격에는 변경하지 않음 |
| SSAFY 1일 차 16시 | PDF §1.2·§2.7에 외부 API 확인 기준이 있다. 기존 인증 증거 파일 기록은 2026-11-19 17:17:57 KST. 팀의 공식 1일 차 날짜 및 기한 이전 증거는 미확인이라 적용 여부 또는 충족 여부를 판단할 수 없다. | 팀 일정·증거를 사용자가 확인하고, 미충족 시 검토자 결정 필요 |

### 제출용 기획 검증 근거 대조

- 외부 API 3종 실제 호출 및 응답 형식·정규화 DTO 대조 자료는 [HTTP 기록](evidence/phase-01-http.md)과 [실행 증거](evidence/phase-01-live.jsonl)에서 확인했다. 기록된 파일 저장 시각은 2026-11-19 17:17:57 KST다.
- 실제 GMS의 연결, Tool 선택 3종 및 Pydantic 인자 검증은 [GMS 증거](evidence/phase-01-gms.jsonl)에서 확인했다. 파일 수정 시각은 2026-11-19 17:44:50 KST다. 이 JSONL에는 개별 요청 시각이 없다.
- 설계 시험에 해당하는 요청 분석, 조회 순서, Tool 간 입력 전달, 제약·재계획 및 캐시 재사용의 실행 결과는 [Phase 2 기록](phase-02.md)과 [대표 실행 로그](evidence/day-03-scenarios.json)에서 확인했다. 해당 증거가 구현 전에 공식 기획 검증으로 수행됐는지는 확인할 수 없다.
- 외부 API와 GMS 증거가 처음 포함된 로컬 Git 커밋은 `d7f0c4a`이며 작성 시각은 2026-11-20 10:05:34 KST다. 파일 및 커밋 시각은 그보다 앞선 공식 검증이나 리뷰어 승인 시각을 입증하지 않는다. 팀 공식 1일 차 일정과 당시 기록을 확보할 때까지 체크리스트 27번은 미확인이다.

## 7. 최종 테스트와 보안

| 구분 | 실행 명령 | 종료 코드·결과 |
|---|---|---|
| 기존 회귀 | `.venv/Scripts/python -m pytest -q --ignore=tests/unit/test_gms_preflight.py` | 0, 31 passed |
| Preflight 로컬 합성 검증 | `.venv/Scripts/python -m pytest -q tests/unit/test_gms_preflight.py` | 0, 6 passed |
| 전체 | `.venv/Scripts/python -m pytest -q` | 0, 37 passed. [출력](evidence/phase-01-final-tests.txt) |
| GMS 실제 | `.venv/Scripts/python -m scripts.verify_gms_preflight` | 0, 연결·선택·무호출 총 5건 HTTP 200. [출력](evidence/phase-01-gms.jsonl) |
| 저장 증거 대조 | Python JSONL·명세 비교, Git 브랜치·인덱스 확인, `.venv/Scripts/python -m pip check` | 0, 보고서와 증거 일치, 의존성 충돌 없음 |
| 보안 재검증 | 기존 보안 절차의 실제 키 비교 목록에 `GMS_KEY` 추가 후 실행 | 0, 실제 키 및 인코딩 변형·토큰 패턴 검출 파일 0. [기존 보안 절차](evidence/phase-01-security.md) |

보안 검사 범위는 Git 인덱스와 커밋 후보 텍스트이며 PDF 원문과 Git 제외 파일은 대상에서 제외했다. 실제 주소·좌표·계약 값이 포함될 수 있는 응답 서브트리는 저장하지 않았다. 이전 증거의 건물 위치와 금액은 필드명·타입과 공개 검증 파라미터로만 나타난다.

## 8. Phase 2 진입 권고

**진입 보류.** 세 API의 연동 증거, 실제 건물 연결 양성 사례, GMS 연결·Tool 호출 사전검증에 대한 기술 차단은 해소됐다. 외부 API 계정별 승인 유형·실제 쿼터, 공식 1일 차 일정 적용 여부, 기존 잠정 설계의 승인 판단이 남았다. GMS 전용 문서·카탈로그 접근 제한과 실호출로 확인한 범위를 구분해 기록했다. Phase 2~4는 미착수다.

REVIEW REQUIRED — 다음 단계 미착수
