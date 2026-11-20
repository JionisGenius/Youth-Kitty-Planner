from .http import government_page

URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"


def titles(session, key, parcel):
    fields = ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji")
    return government_page(session, URL, key, {
        **dict(zip(fields, parcel)), "_type": "json", "numOfRows": 100, "pageNo": 1,
    })
