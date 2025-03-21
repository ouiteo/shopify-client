from typing import Any

import pytest

from shopify_client.builder import ShopifyQuery
from shopify_client.client import ShopifyClient
from shopify_client.exceptions import QueryError
from shopify_client.types import ShopifyWebhookTopic, WebhookSubscriptionInput


async def test_basic_graphql_call(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["getShopName"] = {"data": {"shop": {"name": "Test Store 1"}}}

    query = ShopifyQuery(operation_name="getShopName", entity="shop", fields=["name"])

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql(query)

    assert response == {"data": {"shop": {"name": "Test Store 1"}}}

    # test client with timeout
    async with ShopifyClient("test-store", "access-token", timeout=60.0) as client:
        response = await client.graphql(query)

    assert response == {"data": {"shop": {"name": "Test Store 1"}}}


async def test_graphql_call_with_pagination(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["GetProducts"] = {
        "data": {
            "products": {
                "edges": [
                    {"node": {"id": "1", "title": "Product 1"}},
                    {"node": {"id": "2", "title": "Product 2"}},
                ],
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": None,
                },
            }
        }
    }

    query = ShopifyQuery(
        operation_name="GetProducts",
        entity="products",
        fields=["id", "title", {"name": "pageInfo", "fields": ["hasNextPage", "endCursor"]}],
    )

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql_call_with_pagination(query)

    assert response == [
        {"id": "1", "title": "Product 1"},
        {"id": "2", "title": "Product 2"},
    ]


async def test_graphql_call_with_unrecoverable_error(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["getShopName"] = {
        "error": {
            "data": None,
            "errors": [{"message": "Invalid query syntax"}],
        }
    }

    query = ShopifyQuery(operation_name="getShopName", entity="shop", fields=["name"])

    async with ShopifyClient("test-store", "access-token") as client:
        with pytest.raises(QueryError) as exc_info:
            await client.graphql(query)

    assert "Invalid query syntax" in str(exc_info.value)


async def test_run_bulk_operation_query_with_error(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["currentBulkOperation"] = {
        "error": {
            "data": {
                "bulkOperationRunQuery": {
                    "bulkOperation": None,
                    "userErrors": [{"message": "Invalid query syntax"}],
                }
            }
        }
    }

    query = ShopifyQuery(operation_name="bulkOperation", entity="bulkOperationRunQuery", fields=["userErrors"])

    async with ShopifyClient("test-store", "access-token") as client:
        with pytest.raises(QueryError) as exc_info:
            await client.run_bulk_operation_query(query)

    assert "Invalid query syntax" in str(exc_info.value)


async def test_generate_redirect_url() -> None:
    url = ShopifyClient.generate_redirect_url(
        client_id="test-client",
        scopes=["read_products", "write_products"],
        store="test-store",
        state="test-state",
        redirect_uri="https://example.com/callback",
    )

    expected = (
        "https://test-store/admin/oauth/authorize?"
        "client_id=test-client"
        "&scope=read_products%2Cwrite_products"
        "&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback"
        "&state=test-state"
    )
    assert url == expected


async def test_subscribe_to_topic(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["webhookSubscribe"] = {
        "data": {
            "eventBridgeWebhookSubscriptionCreate": {
                "webhookSubscription": {
                    "id": "gid://shopify/WebhookSubscription/1",
                    "topic": "PRODUCTS_CREATE",
                },
                "userErrors": [],
            }
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        await client.subscribe_to_topic(
            ShopifyWebhookTopic.PRODUCTS_CREATE,
            WebhookSubscriptionInput(
                arn="arn:aws:events:region:account:event-bus/name",
                format="JSON",
            ),
        )
