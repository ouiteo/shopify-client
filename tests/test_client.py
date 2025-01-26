from typing import Any

from shopify_client.client import ShopifyClient


async def test_graphql_call(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["shopName"] = {"data": {"shop": {"name": "Test Store 1"}}}

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql("query shopName{ shop { name } }")

    assert response == {"data": {"shop": {"name": "Test Store 1"}}}


async def test_graphql_call_with_pagination() -> None:
    pass


async def test_graphql_call_with_unrecoverable_error() -> None:
    pass


async def test_graphql_call_with_error_and_retry() -> None:
    pass


async def test_poll_until_complete() -> None:
    pass


async def test_run_bulk_operation_query() -> None:
    pass


async def test_jsonl_pandas_return() -> None:
    pass


async def test_jsonl_jsonlines_return() -> None:
    pass


async def test_run_bulk_operation_query_with_error() -> None:
    pass


async def test_run_bulk_operation_mutation() -> None:
    pass


async def test_run_bulk_operation_mutation_with_error() -> None:
    pass


async def test_parse_query() -> None:
    pass


async def test_proxy_pass() -> None:
    pass


async def test_generate_redirect_url() -> None:
    pass


async def test_get_permanent_token() -> None:
    pass
