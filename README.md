# Youth Kitty Planner · 청년냥이 플래너

희망 지역, 주거 예산과 출근 일정을 바탕으로 독립 준비 계획을 세우는 Vue 3·FastAPI 서비스입니다. 임대차 자료는 과거 신고 거래이며 현재 매물 여부는 확인된 정보가 있을 때만 판단합니다.

## 로컬 실행

레포 루트에서 Python 가상환경과 Node.js 의존성을 설치합니다.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
npm.cmd --prefix frontend ci
```

값이 비어 있는 [.env.example](.env.example)을 참고해 로컬 `.env`에 GMS와 외부 데이터 API 환경변수를 설정합니다. FastAPI와 Vue를 별도 터미널에서 실행합니다.

```powershell
.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm.cmd --prefix frontend run dev
```

브라우저에서 [플래너](http://127.0.0.1:5173/)를 열 수 있습니다. API 계약은 [FastAPI 문서](http://127.0.0.1:8000/docs)에서 확인합니다. Mock 실행, 테스트 결과, 실제 GMS 연결 상태는 [Phase 4 보고서](reports/phase-04.md)에 기록되어 있습니다.

## 기술과 핵심 기능

- Vue 3·Vue Router·Vite로 구성한 대화, 계획 관리, 실행 기록 화면
- FastAPI·Pydantic REST API와 Bearer 세션 인증
- LangGraph와 SSAFY GMS Responses를 이용한 의도 분석 및 조회 계획, 예산·기간 검증과 최대 3회 재계획
- SQLite의 세션별 대화 조건, 계획·작업, 실행 이벤트 저장. 시간이 겹치는 일정은 저장하고 경고 표시
- F3020 실행 이상 징후 판단. 동일 Tool·인자 중복, 재계획 상한 초과, 계획 외 Tool, 계획·실행 불일치를 기록하고 이상 실행만 GMS로 진단

F3020은 일반 서버 실행에 포함됩니다. 실행 이벤트 조회 응답의 마지막 이벤트에서 `payload.anomaly`로 판정과 근거를 확인할 수 있습니다. 증거가 부족하면 `UNKNOWN`을 기록하고 원인 진단을 호출하지 않습니다.

## Mock 시연

실제 GMS 연결이 제한된 상황에서는 아래 명령을 FastAPI 명령 대신 사용합니다. Vue 실행 명령과 접속 주소는 위와 같습니다. 시연 서버는 **합성 GMS·외부 데이터**와 임시 SQLite를 사용합니다.

```powershell
.venv/Scripts/python -m uvicorn ui_preview:create_preview --factory --app-dir tests/integration --host 127.0.0.1 --port 8000
```

1. 다음 문구를 보내고 월세 초과, 재계획 1회, 일부 확인을 실행 타임라인에서 확인합니다. 건축물대장 실패가 표시되어도 과거 거래 결과는 유지됩니다.

   > 서울 종로구(11110) 희망, 보증금 3000만원, 월세 45만원. 2025년 1월 거래. 준비 시작일 2026-11-20, 준비 기간 7일, 출근일 2026-12-01. 대안으로 서울 중구(11140), 서울 용산구(11170), 서울 성동구(11200) 허용

2. `월세만 55만원으로 바꿔줘.`를 보내고 정상 응답 및 기존 준비 날짜를 확인합니다. 초안을 저장한 뒤 작업을 수정하거나 추가합니다.
3. 같은 날짜의 두 작업을 10:00–11:00, 10:30–11:30으로 설정하면 저장 후 중복 경고가 표시됩니다. 시간을 비워 둔 작업은 시간 미정으로 남습니다.
4. `테스트: 호출 제한`을 보내 실패 안내를 확인합니다. 실행 기록 화면에서 성공·일부 확인·실패 결과와 각 실행 이벤트를 조회할 수 있습니다.

## 로컬 검증

```powershell
.venv/Scripts/python -m pytest -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

F3020 회귀 테스트만 실행하려면 `.venv/Scripts/python -m pytest -q tests/integration/test_api.py -k "anomaly_assessment or tool_argument_fingerprints"`를 사용합니다. 합성 이벤트와 Mock GMS로 판정, 호출 분기, HTTP 429 회귀를 검증합니다.

기존 `.env`를 사용해 실제 GMS 연결을 한 번 확인하는 명령은 다음과 같습니다.

```powershell
.venv/Scripts/python -m scripts.verify_gms_preflight --single-request
```

2026-11-20 실제 재검증에서 GMS Responses API가 HTTP 200을 반환했고 `gpt-6.1-sol`이 일치했습니다. Tool 3종의 이름·인자 검증, Vue의 실제 계획 응답·저장·재조회·실행 로그, 합성 이상 이벤트 1건의 실제 GMS 원인 진단을 확인했습니다. 후속 실연동에서 Chrome 응답 표시는 신규 계획 13.0초, 월세 변경 7.5초, 재계획 상한 도달 19.3초였습니다. 이전 HTTP 429는 [보고서](reports/phase-04.md)에 보존했습니다. 대상 사용자의 대기 적합성(NF3005)과 계정별 외부 API 승인·쿼터(NF3007)는 확인 대기입니다.

대외비 표시가 있는 공식 요구사항 PDF는 저장소에 포함하지 않습니다. 해당 원본은 제공받은 로컬 사본을 사용합니다.

## 외부 API 이용 조건

YKP는 Vue 화면, FastAPI 서버, `backend/app/agents/` 실행 로직과 `backend/app/tools/` 제공자 모듈을 분리합니다. 외부 호출은 서버의 주소·키워드 검색, 과거 전월세 조회, 건축물 표제부 조회에 한정합니다. UI는 출처를 표시하며 과거 거래로 현재 임대 가능 여부를 판단하지 않습니다.

| 제공자 | 공개 이용 조건 | 계정에서 확인할 값 |
|---|---|---|
| 카카오 로컬 | 무료 쿼터 적용 앱의 주소·키워드 조회는 공개 일간 제공량이 각각 100,000건입니다. 개발자 계정 기준 최초 활성화 앱에 무료 쿼터가 적용되며 다른 앱 또는 초과 사용에는 유료 설정이 필요할 수 있습니다. [쿼터](https://developers.kakao.com/docs/ko/getting-started/quota) · [카카오맵 정책](https://developers.kakao.com/docs/ko/kakaomap/common) · [운영 정책](https://developers.kakao.com/terms/ko/site-policies) | 앱 관리 → 카카오맵 → 사용 설정에서 활성 상태, 앱 정보에서 무료 쿼터 뱃지, 통계 → 쿼터에서 월·일 한도와 해당 기간 사용량을 확인합니다. [통계 안내](https://developers.kakao.com/docs/ko/getting-started/stat) |
| 국토교통부 연립다세대 전월세 | 무료, 이용허락범위 제한 없음. Phase 1 당시 확인한 공개 개발계정 표기는 10,000건입니다. 지역·계약월로 조회하고 과거 신고 자료로 표시합니다. [공식 데이터와 조건](https://www.data.go.kr/data/15126473/openapi.do) | 공공데이터포털 로그인 → 마이페이지 → 데이터 활용 → Open API에서 개별 활용 신청을 열어 승인 상태, 개발·운영 유형, 적용 트래픽과 사용량, 이용 기간을 확인합니다. |
| 국토교통부 건축HUB 건축물대장 | 무료, 이용허락범위 제한 없음. Phase 1 당시 확인한 공개 개발계정 표기는 10,000건입니다. 표제부 조회로 건물 수준의 일치만 판단합니다. [공식 데이터와 조건](https://www.data.go.kr/data/15134735/openapi.do) · [공공데이터포털 이용 정책](https://www.data.go.kr/ugs/selectPortalPolicyView.do) | 같은 메뉴에서 건축HUB 신청을 따로 열어 승인 상태, 개발·운영 유형, 적용 트래픽과 사용량, 이용 기간을 확인합니다. |

공개 제공량과 실제 계정에 적용된 한도는 별개입니다. 실제 이용 조건 준수 판정에 필요한 관리 화면 자료에는 승인 상태, 유형, 한도, 사용량 및 기간만 남기고 인증키·토큰·계정 식별정보는 가려 주세요.

## 제출 자료

- [요구사항 추적·Agent 설계·REST API 계약](YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md)과 [Tool 입출력 명세](reports/evidence/phase-01-tool-specs.json). 로컬 서버가 실행 중이면 [Swagger UI](http://127.0.0.1:8000/docs)와 [OpenAPI JSON](http://127.0.0.1:8000/openapi.json)을 확인할 수 있습니다.
- [필수 기능 및 Day 3 검증 결과](reports/phase-04.md), [대표 요청 5개의 최종 응답과 전체 로그](reports/evidence/day-03-scenarios.json), Mock 시연 화면 [대화](reports/evidence/day-03-mock-chat.png) · [실행 타임라인](reports/evidence/day-03-mock-timeline.png)
- [SSAFY 공식 셀프 체크리스트](셀프체크리스트.xlsx)와 [외부 API의 공식 출처·공개 이용 조건](reports/phase-01.md). 체크리스트는 운영 환경 응답 시간의 사용 적합성, 계정별 API 승인·쿼터 및 팀 공식 기획 검증 자료를 확인 대기로 기록합니다.

제출용 대표 요청 5건과 스크린샷은 Mock GMS 및 합성 외부 데이터로 제작했습니다. 실제 GMS와 실제 외부 데이터로 수행한 대표 요청의 결과는 [Phase 4 보고서](reports/phase-04.md)에 별도로 기록했습니다.
