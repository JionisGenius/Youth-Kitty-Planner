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

2026-11-20 실제 재검증에서 GMS Responses API가 HTTP 200을 반환했고 `gpt-6.1-sol`이 일치했습니다. Tool 3종의 이름·인자 검증, Vue의 실제 계획 응답·저장·재조회·실행 로그, 합성 이상 이벤트 1건의 실제 GMS 원인 진단을 확인했습니다. 최신 Chrome 측정에서 신규 계획 16.46초, 월세 변경 7.13초, 재계획 3회 상한 도달 22.63초가 걸렸습니다. 대상 사용자의 대기 적합성(NF3005)은 확인 대기입니다. 이전 HTTP 429와 각 실행의 측정 방식은 [Phase 4 보고서](reports/phase-04.md)에 기록했습니다.

대외비 표시가 있는 공식 요구사항 PDF는 저장소에 포함하지 않습니다. 해당 원본은 제공받은 로컬 사본을 사용합니다.

## 외부 API 이용 조건

YKP는 Vue 화면, FastAPI 서버, `backend/app/agents/` 실행 로직과 `backend/app/tools/` 제공자 모듈을 분리합니다. 외부 호출은 서버의 주소·키워드 검색, 과거 전월세 조회, 건축물 표제부 조회에 한정합니다. UI는 출처를 표시하며 과거 거래로 현재 임대 가능 여부를 판단하지 않습니다.

| 제공자 | 공개 이용 조건 | 계정에서 확인할 값 |
|---|---|---|
| 카카오 로컬 | 무료 쿼터 적용 앱의 주소·키워드 조회는 공개 일간 제공량이 각각 100,000건입니다. 개발자 계정 기준 최초 활성화 앱에 무료 쿼터가 적용되며 다른 앱 또는 초과 사용에는 유료 설정이 필요할 수 있습니다. [쿼터](https://developers.kakao.com/docs/ko/getting-started/quota) · [카카오맵 정책](https://developers.kakao.com/docs/ko/kakaomap/common) · [운영 정책](https://developers.kakao.com/terms/ko/site-policies) | 앱 관리 → 카카오맵 → 사용 설정에서 활성 상태, 앱 정보에서 무료 쿼터 뱃지, 통계 → 쿼터에서 월·일 한도와 해당 기간 사용량을 확인합니다. [통계 안내](https://developers.kakao.com/docs/ko/getting-started/stat) |
| 국토교통부 연립다세대 전월세 | 무료, 이용허락범위 제한 없음. Phase 1 당시 확인한 공개 개발계정 표기는 10,000건입니다. 지역·계약월로 조회하고 과거 신고 자료로 표시합니다. [공식 데이터와 조건](https://www.data.go.kr/data/15126473/openapi.do) | 공공데이터포털 로그인 → 마이페이지 → 데이터 활용 → Open API에서 개별 활용 신청을 열어 승인 상태, 개발·운영 유형, 적용 트래픽과 사용량, 이용 기간을 확인합니다. |
| 국토교통부 건축HUB 건축물대장 | 무료, 이용허락범위 제한 없음. Phase 1 당시 확인한 공개 개발계정 표기는 10,000건입니다. 표제부 조회로 건물 수준의 일치만 판단합니다. [공식 데이터와 조건](https://www.data.go.kr/data/15134735/openapi.do) · [공공데이터포털 이용 정책](https://www.data.go.kr/ugs/selectPortalPolicyView.do) | 같은 메뉴에서 건축HUB 신청을 따로 열어 승인 상태, 개발·운영 유형, 적용 트래픽과 사용량, 이용 기간을 확인합니다. |

2026-11-20 실제 관리 화면에서 카카오맵 활성화와 무료 쿼터 적용을 확인했습니다. 콘솔의 15:00 KST 집계는 주소 17/100,000건, 키워드 3/100,000건이었습니다. 두 공공 API는 모두 개발계정 승인, 적용 기간 2026-11-19~2028-11-19, 사용 기능별 일일 10,000건이었습니다. 공공데이터포털의 확인 화면에서는 누적 호출량을 확인하지 못했습니다. [계정별 승인·한도 화면](reports/evidence/checklist-26-account-quotas.png)

카카오 검색은 Tool 호출당 1회, 전월세는 지역·계약월당 페이지당 100건과 최대 20페이지, 건축HUB는 필지별 표제부 첫 페이지 100건을 조회합니다. 충분한 거래가 확보되면 페이지 탐색을 멈추고, 동일 Tool·인자 결과는 실행 중 재사용합니다. 제공자 HTTP 자동 재시도는 없고, 조건 재계획은 사용자 허용 범위에서 최대 3회입니다. [정책·코드 대조](reports/phase-01.md#26번-공개-정책과-실제-적용량)

## 제출 자료

- [요구사항 추적·Agent 설계·REST API 명세](YKP_codex_handoff_v1/docs/ARCHITECTURE_AND_SCHEMA_v1.md), [Tool 입출력 명세](reports/evidence/phase-01-tool-specs.json), [Swagger 화면](reports/evidence/checklist-docs.png)
- [백엔드 소스](backend/app/), [Vue 소스](frontend/src/), [테스트](tests/), [이 README](README.md)
- [대표 요청 5건의 결과·전체 로그·재계획 사례](reports/evidence/day-03-scenarios.json), [기능 검증 및 F3020 비교](reports/phase-04.md), [전체 화면 증빙](reports/evidence/)
- [외부 API 실행 기록](reports/evidence/phase-01-live.jsonl), [실제 GMS Tool Calling](reports/evidence/phase-01-gms.jsonl), [제약·재계획 시험](reports/phase-02.md), [기획 검증 시각의 출처](reports/phase-01.md#제출용-기획-검증-근거-대조)
- [공식 셀프 체크리스트](셀프체크리스트.xlsx), [실제 대기 화면](reports/evidence/checklist-23-live-wait.png), [재계획 상한 화면](reports/evidence/checklist-23-live-result.png), [기획 검증 이력 화면](reports/evidence/checklist-27-planning-records.png)

제출용 대표 요청 5건과 스크린샷은 Mock GMS 및 합성 외부 데이터로 제작했습니다. 실제 GMS와 실제 외부 데이터로 수행한 대표 요청의 결과는 [Phase 4 보고서](reports/phase-04.md)에 별도로 기록했습니다.
