# Phase 1 HTTP 실행 증거

실행일 2026-11-19 (KST), Python 3.11.9, 공식 HTTPS 제공자. 최종 인증 증거 파일 기록 시각은 17:17:57 KST다. 인증키·인증 헤더·요청 전체 URL·주소·좌표·계약 금액·건축물 번호 값은 보관하지 않았다. 새 증거는 허용 목록에 있는 필드명과 타입, 결과 코드, 건수, 소요 시간, 매칭 상태만 담는다.

## 재현 명령

| 구분 | 명령 | 종료 |
|---|---|---|
| 인증된 정상·빈·오류, 페이지, 실제 후보 연결 | `.venv/Scripts/python -m scripts.verify_external_apis --extended --match` | 0. [실행 결과 JSONL](phase-01-live.jsonl) |
| 가짜 인증값의 실제 HTTP 오류 | `.venv/Scripts/python -m scripts.verify_external_apis --invalid-credentials` | 0. [인증 오류 JSONL](phase-01-invalid-auth.jsonl) |
| 기존 및 신규 Mock·Unit | `.venv/Scripts/python -m pytest -q` | 0. [별도 테스트 출력](phase-01-tests.txt) |

가짜 인증값 실행의 종료 0은 예상한 AUTH_FAILED 4건을 확인했다는 의미다. 수집된 JSONL은 Mock 없이 공식 제공자를 호출한 결과다. DTO 입출력 회귀, 비밀값 필터, 실제 서비스에서 유도하지 않은 429·5xx·타임아웃은 pytest 증거를 참조한다.

## 인증된 실제 응답

시간은 요청 및 해당 검사 처리 시간이며 페이지 테스트는 두 요청 합산이다.

| 서비스 / 검사 | HTTP | 제공자 코드 | 관찰 결과 | 시간 |
|---|---|---|---|---|
| 카카오 주소 / 키워드 | 200 / 200 | — | 주소 2건, 키워드 첫 페이지 5건. 각 AMBIGUOUS | 203 / 47 ms |
| 카카오 빈 주소 | 200 | — | NO_RESULT, documents 0건 | 32 ms |
| 카카오 잘못된 size | 400 | 오류 타입 허용 목록 외 | INVALID_ARGUMENT | 15 ms |
| MOLIT 전월세 2025-01 | 200 | 000 | 첫 페이지 원본 100건, 총 197건, Tool limit 3으로 3건 | 281 ms |
| MOLIT 기본월 | 200 | 000 | requested_period null, effective_period 202610, 총 116건, Tool 1건 | 63 ms |
| MOLIT 빈 월 | 200 | 000 | 2000-01 요청의 총 건수 0, 내부 count 0 | 31 ms |
| MOLIT 지역코드 생략 / Tool에서 생략 | 200 / 요청 없음 | 000 / — | 제공자는 빈 결과, Tool은 INVALID_ARGUMENT | 15 / 0 ms |
| MOLIT 문자열 numOfRows 진단 | 200 | 04 | XML 게이트웨이 오류, SERVICE_UNAVAILABLE | 16 ms |
| 건축HUB 다건 필지 | 200 | 00 | 표제부 34건, AMBIGUOUS | 531 ms |
| 건축HUB 빈 필지 | 200 | 00 | 0건, NOT_FOUND | 47 ms |
| MOLIT 1·2페이지 | 200 / 200 | 000 / 000 | 각 2행, 총 197, 페이지 번호 1·2, 행 내용 다름 | 78 ms |
| 건축HUB 1·2페이지 | 200 / 200 | 00 / 00 | 각 2행, 총 34, 페이지 번호 1·2, 행 내용 다름 | 141 ms |

조회 입력은 카카오 공개 장소 예시, MOLIT 지역 11110·계약월 202501 또는 직전 완료월, 건축HUB 공식 샘플 필지와 비어 있는 필지 예시다. 실제 후보 주소의 값은 증거에서 제외했다. MOLIT DTO는 유효한 5자리 시군구와 YYYYMM를 검증하고, 데이터의 행별 시군구·계약월도 대조한다. 두 페이지 테스트로 전량 무누락을 입증하지는 않으며 최대 페이지 정책과 다건 판정을 보고서에 명시했다.

## 필드 타입 및 비식별화된 구조

- 카카오 JSON `meta`와 `documents[]`. 주소 행은 `address_name`, `x`, `y`가 문자열이다. `address` 내부 `b_code`, `h_code`, `main_address_no`, `sub_address_no`도 문자열이다. 법정동과 행정동의 값이 다른 행을 실제 관찰했다. 키워드 행은 `id`, `place_name`, `place_url`, `address_name`, `road_address_name`, `x`, `y`가 문자열이다. Tool은 좌표를 float로, 두 코드를 각각 문자열로 유지한다. [공식 로컬 명세](https://developers.kakao.com/docs/ko/local/dev-guide)
- MOLIT XML `response/header/{resultCode,resultMsg}`, `response/body/items/item[]`, `pageNo/numOfRows/totalCount`. 실측 행의 `sggCd`, `umdNm`, `jibun`, `mhouseNm`, `dealYear/dealMonth/dealDay`, `deposit`, `monthlyRent`, `floor`, `excluUseAr`는 XML 문자열이다. 공식 페이지의 Swagger GET 응답 스키마에서 `deposit`과 `monthlyRent` 모두 만원 단위로 확인했다. 내부 DTO는 두 값에 10,000을 곱한 정수 원화, 계약일 date, 전용면적 float, 층 int로 정규화한다. 정규화 실 결과에는 `is_historical=true`가 포함됐다. [공식 Swagger·오류표](https://www.data.go.kr/data/15126473/openapi.do)
- 건축HUB JSON `response/header`, `response/body/items/item[]`. 실측 필지 코드 5종, `bldNm`, `useAprDay`, `mainPurpsCdNm`, `newPlatPlc`, `platPlc`는 문자열, `mgmBldrgstPk`, `grndFlrCnt`, `hhldCnt`는 정수였다. 일치 사례에서 내부 건축물 PK는 문자열, 승인일은 date, 층·세대수는 int였다. 실제 키 값과 속성 값은 수집 증거에서 제외했다. [공식 표제부 명세·오류표](https://www.data.go.kr/data/15134735/openapi.do)

## 실제 건물 연결

| 검사 | 주소 응답 | 표제부 HTTP/코드 | 판정 | 소요 시간 |
|---|---|---|---|---|
| 후보 1 | 200 / RESOLVED | 200 / 00, 1건 | UNKNOWN / 표제부 이름 없음 | 47 + 47 ms |
| 후보 2 | 200 / RESOLVED | 200 / 00, 1건 | UNKNOWN / 표제부 이름 없음 | 47 + 46 ms |
| 후보 3 | 200 / RESOLVED | 200 / 00, 1건 | MATCHED_BUILDING / 이름 확인 | 32 + 62 ms |

집계는 시도 3, 표제부 요청 3, MATCHED_BUILDING 1, AMBIGUOUS 0, NOT_FOUND 0, UNKNOWN 2, 제공자 오류 0이다. 세 건에서 `sggCd`와 카카오 법정동 `b_code`, 지번에서 추출한 대지 구분·본번·부번을 표제부의 `sigunguCd/bjdongCd/platGbCd/bun/ji`와 대조했다. 양성 1건은 거래 `mhouseNm`과 표제부 `bldNm`까지 일치했다. 내부 후보 ID가 상세 Tool 응답에 유지됐음을 각 건에서 검증했다. 하나의 지역·월과 작은 표본이며 결과는 건물 수준이다. 과거 거래가 현재 임대 가능한 매물임을 나타내지는 않는다.

## 실제 인증 거부 및 이전 기록

| 서비스 | HTTP / 제공자 코드 | 결과 | 시간 |
|---|---|---|---|
| 카카오 주소 / 키워드 | 401 / AccessDeniedError | AUTH_FAILED 두 건 | 203 / 16 ms |
| MOLIT 전월세 | 403 / XML 게이트웨이 30 | AUTH_FAILED | 219 ms |
| 건축HUB | 403 / JSON 게이트웨이 30 | AUTH_FAILED | 15 ms |

초기 Phase 1 기록에서는 키가 설정되지 않아 정상 모드가 HTTP 0건으로 종료 1이었다. 그때의 가짜 인증값은 카카오 주소·키워드 401/401, MOLIT·건축HUB 403/403이었다. 이번 보완의 첫 기본 샌드박스 실행은 키 설정을 확인했으나 HTTP 응답 없이 SERVICE_UNAVAILABLE이었다. 네트워크가 허용된 공식 API 실행에서 정상 응답을 확보했다. 앞선 실검증 시도에서 제공자가 지역코드 누락을 오류로 응답할 것이라는 기대는 실패했다. 위의 최종 증거는 제공자 동작과 DTO 사전 차단을 각각 검증한다.

**REVIEW REQUIRED — 다음 단계 미착수**
