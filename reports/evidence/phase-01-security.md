# Phase 1 보안 검증

검사 범위는 Git 인덱스 및 커밋 후보 텍스트 전체다. Python 코드, 테스트 fixture, 예시 환경 설정, 보고서와 JSONL을 포함한다. PDF 원본은 텍스트 검사 범위에서 제외했다. Git으로 제외된 로컬 `.env`는 설정과 로드 여부를 확인했다. 실제 키는 비교에만 사용했으며 값을 출력하지 않았다.

## 실행 명령

레포 루트에서 아래 PowerShell 명령을 실행한다. 결과는 카운트만 반환한다.

```powershell
@'
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, quote_plus, unquote

from backend.app.core.config import load_api_keys


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, check=False)


indexed = git("ls-files", "-z")
listed = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
assert indexed.returncode == listed.returncode == 0
keys = load_api_keys()
assert all(keys.values())
assert git("check-ignore", "-q", "--", ".env").returncode == 0
assert git("check-ignore", "-q", "--", ".env.example").returncode == 1
assert Path(".env.example").read_text("ascii").splitlines() == [
    "KAKAO_REST_API_KEY=", "MOLIT_RENT_API_KEY=", "BUILDING_HUB_API_KEY=",
]

patterns = re.compile(
    r"sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
)
variants = set()
for key in keys.values():
    plain = unquote(key)
    variants.update((key, plain, quote(plain, safe=""), quote_plus(plain, safe="")))

files = {Path(item.decode("utf-8")) for item in listed.stdout.split(b"\0") if item}
texts = [file.read_text("utf-8-sig") for file in files if file.suffix.lower() != ".pdf"]
known_hits = sum(any(value in body for value in variants) for body in texts)
pattern_hits = sum(bool(patterns.search(body)) for body in texts)
print({"tracked": len(indexed.stdout.split(b"\0")) - 1,
       "scanned_text_files": len(texts), "configured_provider_keys": len(keys),
       "configured_key_hit_files": known_hits, "token_pattern_hit_files": pattern_hits})
raise SystemExit(int(bool(known_hits or pattern_hits)))
'@ | .venv/Scripts/python -
```

## 결과

종료 코드는 0이었다. Git 추적 파일 0개, 커밋 후보 텍스트 29개, 로드된 제공자 키 3종이었다. 실제 키 또는 인코딩 변형이 검출된 파일 0개, 일반 토큰 패턴이 검출된 파일 0개였다.

`git check-ignore -v -- .env .env.local backend/data/cache.sqlite .venv/ reports/evidence/raw/example.json`은 다섯 경로가 모두 제외됨을 확인했다. 예시 환경 파일은 커밋 후보에 포함된다.

Tool 응답의 비밀값·원문 오류 제거와 HTTP 증거의 허용 필드·타입만 저장하는 동작을 별도 pytest로 검사했다. [테스트 결과](phase-01-final-tests.txt)

**REVIEW REQUIRED — 다음 단계 미착수**
