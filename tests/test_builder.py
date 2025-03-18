from typing import Any, Literal

import pytest
from typing_extensions import TypedDict

from shopify_client.builder import ShopifyQuery

from tests.conftest import json_fixture


class QueryTestCase(TypedDict):
    test_name: str
    entity: str
    fields: list[Any]
    args: dict[str, Any] | None
    query_type: Literal["query", "mutation"]
    expected: str


@pytest.mark.parametrize("test_case", json_fixture("shopify_queries.json"), ids=lambda x: x["test_name"])
def test_query_builder(test_case: QueryTestCase) -> None:
    """
    Parameterized test for the Shopify GraphQL query builder.
    Tests various query scenarios including simple queries, connections, nested fields,
    mutations, and different argument types.
    """
    query = str(
        ShopifyQuery(
            entity=test_case["entity"],
            fields=test_case["fields"],
            args=test_case["args"],
            query_type=test_case["query_type"],
        )
    )

    assert query == test_case["expected"]
