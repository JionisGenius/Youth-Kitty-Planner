# YKP 저장소 구조

```text
.
├── backend/app/
│   ├── agents/             # LangGraph, GMS Planner, 세션 Memory
│   ├── api/                # FastAPI 라우터·인증
│   ├── core/               # 환경설정, GMS Responses 클라이언트
│   ├── db/                 # SQLite 스키마와 저장소
│   ├── events/             # Publisher, Logging Agent, F3020
│   ├── schemas/            # Pydantic API·Tool·Agent·이벤트 모델
│   ├── services/           # 정규화, 매칭, 제약과 재계획
│   └── tools/              # Registry, Executor, 외부 제공자
├── frontend/               # 별도 Vue·Vite 화면 및 프론트엔드 테스트
├── tests/                  # Python 단위·통합 테스트와 Mock 시연 서버
├── scripts/                # 실제 GMS·외부 API 검증 명령
├── YKP_codex_handoff_v1/
│   └── docs/               # 구현 계약과 저장소 구조
├── reports/
│   ├── verification.md     # 제출용 통합 검증
│   └── evidence/           # 정제한 화면·실행 로그·Tool 명세
├── requirements.txt        # 런타임·개발·테스트 Python 의존성
├── 셀프체크리스트.xlsx
└── README.md
```

Vue는 FastAPI의 Bearer 인증 REST API를 사용합니다. Agent는 Tool Gateway를 통해 제공자를 호출하고 정규화된 데이터를 받아 제약을 판단합니다. 세션 Checkpointer와 계획·실행 이벤트 SQLite 저장소의 책임을 분리합니다. Logging Agent는 정제 이벤트를 순번대로 저장하며, F3020은 이상 판정에만 GMS 진단을 요청합니다.

[구현 계약과 요구사항 추적](ARCHITECTURE_AND_SCHEMA_v1.md) · [설치와 시연](../../README.md) · [통합 검증과 제출 증거](../../reports/verification.md)
