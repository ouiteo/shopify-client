from typing import Any

import pytest

from shopify_client.utils import create_paginated_query, get_error_codes


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


def test_create_paginated_query() -> None:
    response = create_paginated_query("products", ["id", "title", "handle", "createdAt"], first=10)
    assert response.name == "getProducts"
