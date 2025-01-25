import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonlines import Reader
from pytest_httpx import HTTPXMock

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def json_fixture(file_name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES_DIR / file_name).read_text())
    return data


def jsonl_fixture(file_name: str) -> Reader:
    data: dict[str, Any] = json.loads((FIXTURES_DIR / file_name).read_text())
    reader = Reader(data)
    return reader


@pytest.fixture
def mock_shopify_api(httpx_mock: HTTPXMock) -> dict[str, Any]:
    """
    Mock out Shopify graphql responses using the dictionary returned from this fixture, works with queries or mutations
    usage:

    def my_test(mock_shopify_api: dict[str, dict[str, Any]]):
        mock_shopify_api["shopName"] = {"data": {"shop": {"name": "Test Store 1"}}}
        response = client.execute("query shopName{ shop { name	} }")

        assert response == {"data": {"shop": {"name": "Test Store 1"}}}

    """
    responses: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        query_name_matches = re.search(r"(?:query|mutation)\s+(\w+)", request.content.decode())
        if not query_name_matches:
            raise ValueError("Could not find query name in request, please use query/mutation <name>{...}")

        query_name = query_name_matches.group(1)
        if query_name not in responses:
            current_test = os.getenv("PYTEST_CURRENT_TEST", "unknown")
            raise ValueError(f"Test: {current_test} -> Response not mocked out for {query_name}")

        data = responses[query_name]
        return httpx.Response(200, json=data)

    pattern = re.compile(r"https://.*.myshopify.com/.*")
    httpx_mock.add_callback(handler, url=pattern)

    return responses
