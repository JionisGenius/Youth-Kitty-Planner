from datetime import date, timedelta

from ..schemas.agent import ConstraintEvaluation, PlanDraft, TaskDraft, UserConstraints
from ..schemas.tools import RentalCandidate


def _assessment(rule, expected, observed, passed, refs=(), caveat=None):
    status = "UNKNOWN" if observed is None else "PASS" if passed else "FAIL"
    return ConstraintEvaluation(rule_code=rule, status=status, expected_value=expected,
                                observed_value=observed, source_refs=list(refs), caveat=caveat,
                                reason_code={"UNKNOWN": "NOT_VERIFIED", "PASS": "WITHIN_LIMIT",
                                             "FAIL": "LIMIT_EXCEEDED"}[status])


def rental_evaluations(candidate: RentalCandidate, constraints: UserConstraints):
    pairs = (
        ("HISTORICAL_DEPOSIT", constraints.max_deposit_krw, candidate.deposit_krw),
        ("HISTORICAL_RENT", constraints.max_monthly_rent_krw, candidate.monthly_rent_krw),
    )
    return [_assessment(rule, limit, value, value is not None and value <= limit, candidate.evidence_refs)
            for rule, limit, value in pairs if limit is not None]


def rental_priority(candidate, constraints):
    statuses = {result.status for result in rental_evaluations(candidate, constraints)}
    return 2 if "FAIL" in statuses else 1 if "UNKNOWN" in statuses else 0


def preparation_end(constraints: UserConstraints):
    start, days = constraints.planning_start_date, constraints.preparation_days
    if start is None or days is None or days - 1 > (date.max - start).days:
        return None
    return start + timedelta(days=days - 1)


def planning_evaluations(constraints: UserConstraints):
    checks = []
    end = preparation_end(constraints)
    deadline = constraints.job_start_date
    if deadline is not None or constraints.preparation_days is not None:
        finish = end.isoformat() if end is not None and deadline is not None else None
        expected = deadline.isoformat() if deadline else None
        caveat = "준비 시작일부터 기간을 세고 출근 전날까지 준비를 마칩니다."
        days = constraints.preparation_days
        if end is None and deadline is not None and days is not None and days < deadline.toordinal():
            latest_start = deadline - timedelta(days=days)
            caveat += f" {days}일을 확보하려면 늦어도 {latest_start.isoformat()}에 시작해야 합니다."
        checks.append(_assessment("PLAN_TIMELINE", expected, finish,
                                  end is not None and deadline is not None and end < deadline,
                                  caveat=caveat))
    for rule, limit, caveat in (
        ("MAINTENANCE_FEE", constraints.max_maintenance_fee_krw, "관리비 자료가 없습니다."),
        ("COMMUTE_TIME", constraints.max_commute_minutes, "경로와 출근 시간대 소요 시간을 확인해야 합니다."),
    ):
        if limit is not None:
            ceiling = f"{limit:,}원" if rule == "MAINTENANCE_FEE" else f"{limit}분"
            checks.append(_assessment(rule, limit, None, False,
                                      caveat=f"{caveat} 실제 값이 {ceiling} 이하인지 확인해 주세요."))
    return checks


def draft_plan(state):
    constraints = state["user_constraints"]
    start, end = constraints.planning_start_date, preparation_end(constraints)
    deadline = constraints.job_start_date
    if deadline is not None:
        task_start = start if start is not None and start < deadline else None
        task_end = end if end is not None and end < deadline else None
    else:
        task_start, task_end = start, end
    candidate = state.get("selected_candidate")
    if candidate:
        tasks = [
            TaskDraft(title="과거 전월세 사례와 예산 비교", task_date=task_start,
                      description="후보별 월세와 보증금의 검증 결과를 비교합니다."),
            TaskDraft(title="현재 매물과 실제 부대비용 확인", task_date=task_end,
                      description="현재 임대 여부, 관리비, 출퇴근 경로와 계약 서류를 별도로 확인합니다."),
        ]
    else:
        tasks = [
            TaskDraft(title="찾아본 사례와 예산 상한 재검토", task_date=task_start,
                      description="예산을 유지하면서 확인할 수 있는 지역 또는 조회 범위를 다시 선택합니다."),
            TaskDraft(title="현재 매물과 실제 부대비용 확인", task_date=task_end),
        ]
    return PlanDraft(title="독립 준비 계획 초안", constraints=constraints,
                     planning_start_date=start, planning_end_date=end, tasks=tasks,
                     evaluations=state["constraint_results"],
                     source_refs=[source.ref for source in state.get("sources", [])],
                     warnings=state.get("warnings", []))

