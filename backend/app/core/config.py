from os import getenv
from pathlib import Path

from dotenv import load_dotenv

KEY_NAMES = {
    "kakao_local": "KAKAO_REST_API_KEY",
    "molit_rent": "MOLIT_RENT_API_KEY",
    "building_hub": "BUILDING_HUB_API_KEY",
}


def load_api_keys() -> dict[str, str]:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False, interpolate=False)
    return {provider: getenv(name, "").strip() for provider, name in KEY_NAMES.items()}
