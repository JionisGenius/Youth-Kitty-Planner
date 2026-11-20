from .http import ProviderError, government_page

URL = "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent"


def pages(session, key, district, month):
    seen = 0
    expected_total = None
    for page in range(1, 21):
        rows, total = government_page(session, URL, key, {
            "LAWD_CD": district, "DEAL_YMD": month, "pageNo": page, "numOfRows": 100,
        })
        if expected_total is not None and expected_total != total:
            raise ProviderError("DATA_INCOMPLETE")
        expected_total = total
        seen += len(rows)
        if seen > total or (not rows and seen < total):
            raise ProviderError("SCHEMA_MISMATCH")
        yield from rows
        if seen == total:
            return
    raise ProviderError("DATA_INCOMPLETE")

