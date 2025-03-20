from typing import Any


def get_error_codes(data: dict[str, Any]) -> set[str]:
    codes = set()
    for error in data.get("errors", []):
        codes.add(error.get("extensions", {}).get("code"))
    if data.get("error"):
        codes.add(data.get("error", {}).get("extensions", {}).get("code"))

    return codes
