from typing import Any

import pytest

from shopify_client.utils import get_error_codes


@pytest.mark.parametrize(
    "data",
    [
        {
            "errors": [
                {
                    "message": "Throttled",
                    "extensions": {"code": "THROTTLED", "documentation": "https://shopify.dev/api/usage/rate-limits"},
                }
            ]
        },
        {
            "error": {
                "message": "Throttled",
                "extensions": {"code": "THROTTLED", "documentation": "https://shopify.dev/api/usage/rate-limits"},
            }
        },
    ],
)
def test_get_error_codes(data: dict[str, Any]) -> None:
    assert get_error_codes(data) == {"THROTTLED"}
