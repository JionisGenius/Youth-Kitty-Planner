"""Local Mock GMS and provider fixture for Phase 4 browser checks."""

from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.agents.graph import BUILDING
from backend.app.agents.planner import PlannerError
from backend.app.main import create_app
from backend.app.schemas.agent import Analysis, ConstraintPatch

from test_agent import Provider, create_plan


class PreviewPlanner:
    def analyze(self, message, prior):
        if message == "테스트: 호출 제한":
            raise PlannerError("RATE_LIMITED")
        if message == "테스트: 인증 설정":
            raise PlannerError("AUTH_FAILED")
        if "월세만 55만원" in message:
            return Analysis(intent="UPDATE_CONSTRAINT", patch=ConstraintPatch(max_monthly_rent_krw=550_000),
                            evidence={"max_monthly_rent_krw": "월세만 55만원"})
        if "서울 종로구(11110)" in message:
            if "월세 45만원" in message and "대안으로" in message:
                analysis = create_plan(1, max_monthly_rent_krw=450_000)
                analysis.evidence["max_monthly_rent_krw"] = "월세 45만원"
                return analysis
            return create_plan()
        return Analysis(intent="GENERAL")

    def plan(self, intent, tool, args):
        return tool, args


class PreviewProvider(Provider):
    def __call__(self, tool, args):
        if tool == BUILDING and args["sigungu_code"] == "11140":
            return Provider(failure=(BUILDING, "TIMEOUT"))(tool, args)
        return super().__call__(tool, args)


def create_preview():
    folder = TemporaryDirectory(prefix="ykp-ui-fixture-")
    root = Path(folder.name)
    app = create_app(database_path=root / "business.sqlite3", checkpoint_path=root / "memory.sqlite3",
                     planner=PreviewPlanner(), run_tool=PreviewProvider(rents={"11140": 450_000}))
    app.state.preview_directory = folder
    return app
