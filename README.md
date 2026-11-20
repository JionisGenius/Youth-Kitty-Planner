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

대외비 표시가 있는 공식 요구사항 PDF는 저장소에 포함하지 않습니다. 해당 원본은 제공받은 로컬 사본을 사용합니다.
