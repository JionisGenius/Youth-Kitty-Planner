from .http import fetch

BASE_URL = "https://dapi.kakao.com/v2/local"


def search(session, key, args):
    endpoint = "address" if args.mode == "ADDRESS" else "keyword"
    params = {"query": args.query, "size": args.limit}
    if args.mode == "ADDRESS":
        params["analyze_type"] = "exact"
    return fetch(session, f"{BASE_URL}/search/{endpoint}.json", params,
                 {"Authorization": f"KakaoAK {key}"}).json()
