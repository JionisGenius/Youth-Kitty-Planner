import re

from ..schemas.agent import Analysis, LocationCondition, UserConstraints

MONEY_LABELS = {
    "max_deposit_krw": ("보증금", "전세금"),
    "max_monthly_rent_krw": ("월세", "임대료"),
    "max_maintenance_fee_krw": ("관리비",),
}
DATE_LABELS = {
    "planning_start_date": ("준비", "계획", "시작"),
    "job_start_date": ("출근", "입사"),
}
MONEY_SPLIT = re.compile("(" + "|".join(label for labels in MONEY_LABELS.values() for label in labels) + ")")


def _won_amounts(quote):
    for number, unit in re.findall(r"(?<![0-9,.-])([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(천만|백만|십만|만|천|억)?\s*원", quote):
        if "." in number:
            whole, fraction = number.replace(",", "").split(".")
        else:
            whole, fraction = number.replace(",", ""), ""
        numerator = int(whole + fraction)
        multiplier = {None: 1, "": 1, "천": 1_000, "만": 10_000, "십만": 100_000,
                      "백만": 1_000_000, "천만": 10_000_000, "억": 100_000_000}[unit]
        amount, remainder = divmod(numerator * multiplier, 10 ** len(fraction))
        if remainder == 0:
            yield amount
    for lead, unit, trailing in re.findall(r"(?<![0-9,.-])([0-9]+)\s*(억|천|백|십)\s*([0-9]+)?\s*만원", quote):
        multiplier = {"억": 100_000_000, "천": 10_000_000, "백": 1_000_000, "십": 100_000}[unit]
        yield int(lead) * multiplier + int(trailing or 0) * 10_000
    if not re.search(r"원", quote):
        for number in re.findall(r"(?<![0-9,.-])([0-9]+(?:,[0-9]{3})*)\s*만(?![0-9])", quote):
            yield int(number.replace(",", "")) * 10_000


def _locations(value, quote):
    locations = [value] if isinstance(value, LocationCondition) else value
    accepted = []
    for location in locations:
        if location.label not in quote or not re.search(r"[가-힣A-Za-z]", location.label):
            return None
        code = location.sigungu_code
        if code is not None and not re.search(
            rf"{re.escape(location.label)}\s*(?:[:(]\s*)?(?:(?:시군구\s*)?코드\s*)?{code}(?![0-9])"
            rf"|(?<![0-9]){code}\s*[:(]?\s*{re.escape(location.label)}", quote
        ):
            return None
        # Retain a regional label, not a detailed personal address or model-generated coordinates.
        if re.search(r"[0-9]|[\n\r]", location.label):
            return None
        accepted.append(LocationCondition(label=location.label, sigungu_code=code))
    return accepted[0] if isinstance(value, LocationCondition) else accepted


def _ground(field, value, quote):
    if field in MONEY_LABELS:
        parts = MONEY_SPLIT.split(quote)
        return value if any(
            label in MONEY_LABELS[field] and value in _won_amounts(fragment)
            for label, fragment in zip(parts[1::2], parts[2::2])
        ) else None
    if field in DATE_LABELS:
        dates = re.findall(r"(?<![0-9])([0-9]{4})\s*(?:년|[-./])\s*([0-9]{1,2})\s*(?:월|[-./])\s*([0-9]{1,2})", quote)
        wanted = (value.year, value.month, value.day)
        return value if any(label in quote for label in DATE_LABELS[field]) and any(
            tuple(map(int, parts)) == wanted for parts in dates
        ) else None
    if field == "max_commute_minutes":
        return value if ("통근" in quote or "출퇴근" in quote) and value in {
            int(n) for n in re.findall(r"([0-9]+)\s*분", quote)
        } else None
    if field == "preparation_days":
        days = (int(n) * (7 if unit == "주" else 1)
                for n, unit in re.findall(r"(?<![0-9-])([0-9]+)\s*(일|주)(?:간)?(?![가-힣])", quote))
        return value if "준비" in quote and value in days else None
    if field == "transport_mode":
        labels = {"TRANSIT": ("대중교통", "지하철", "버스"), "WALKING": ("도보",), "DRIVING": ("차량", "자차", "운전")}
        return value if any(label in quote for label in labels[value]) else None
    if field == "allowed_alternative_areas" and (
        not re.search(r"대안|대체|허용|가능|괜찮", quote) or re.search(r"불가|제외|않|안 돼", quote)
    ):
        return None
    if field in {"work_location", "residential_preferences", "allowed_alternative_areas"}:
        return _locations(value, quote)
    return None


def apply_patch(previous: UserConstraints, previous_month: str | None, analysis: Analysis, message: str):
    updates = {}
    unverified = []
    for field in type(analysis.patch).model_fields:
        if field not in analysis.patch.model_fields_set or (value := getattr(analysis.patch, field)) is None:
            continue
        quote = analysis.evidence.get(field, "")
        verified = _ground(field, value, quote) if quote and quote in message else None
        if verified is None:
            unverified.append(field)
        elif verified != getattr(previous, field):
            updates[field] = verified
    month = previous_month
    changed = list(updates)
    if analysis.contract_month is not None:
        quote = analysis.evidence.get("contract_month", "")
        parts = re.findall(r"(?<![0-9])([0-9]{4})\s*년\s*([0-9]{1,2})\s*월", quote)
        compact = re.findall(r"(?<![0-9])[0-9]{6}(?![0-9])", quote)
        months = compact + [year + value.zfill(2) for year, value in parts]
        if quote and quote in message and analysis.contract_month in months:
            month = analysis.contract_month
            if month != previous_month:
                changed.append("contract_month")
        else:
            unverified.append("contract_month")
    constraints = previous.model_copy(update={
        **updates, "fixed_fields": previous.fixed_fields | set(updates),
    })
    return constraints, month, changed, unverified

