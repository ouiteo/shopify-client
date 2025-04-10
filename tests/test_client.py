from typing import Any

import pytest
from graphql_query import Field, Operation, Query

from shopify_client.client import ShopifyClient
from shopify_client.exceptions import QueryError, ShopUnavailableException
from shopify_client.types import EventBridgeWebhookSubscriptionInput, ShopifyWebhookTopic

from tests.conftest import json_fixture


async def test_basic_graphql_call(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["getShopName"] = {"data": {"shop": {"name": "Test Store 1"}}}

    query = Operation(type="query", name="getShopName", queries=[Query(name="shop", fields=["name"])])

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

    query = Operation(
        type="query",
        name="GetProducts",
        queries=[
            Query(name="products", fields=["id", "title", Field(name="pageInfo", fields=["hasNextPage", "endCursor"])])
        ],
    )

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql_call_with_pagination(query)

    assert response == [
        {"id": "1", "title": "Product 1"},
        {"id": "2", "title": "Product 2"},
    ]


async def test_graphql_paginated_no_pageinfo(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["GetProducts"] = {
        "data": {
            "products": {
                "edges": [{"node": {"id": "1", "title": "Product 1"}}, {"node": {"id": "2", "title": "Product 2"}}]
            }
        }
    }

    query = Operation(
        type="query",
        name="GetProducts",
        queries=[
            Query(name="products", fields=["id", "title", Field(name="pageInfo", fields=["hasNextPage", "endCursor"])])
        ],
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

    query = Operation(type="query", name="getShopName", queries=[Query(name="shop", fields=["name"])])

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

    query = Query(name="bulkOperationRunQuery", fields=["userErrors"])

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
    mock_shopify_api["eventBridgeWebhookSubscriptionCreate"] = {
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
        await client.eventbridge_subscribe_to_topic(
            ShopifyWebhookTopic.PRODUCTS_CREATE,
            EventBridgeWebhookSubscriptionInput(
                arn="arn:aws:events:region:account:event-bus/name",
                format="JSON",
            ),
        )


async def test_shop_not_available(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["unavailableStore"] = {
        "error": {"data": None, "errors": [{"message": "This is error msg"}], "status": 402}
    }
    query = Operation(type="query", name="unavailableStore", queries=[Query(name="shop", fields=["name"])])
    async with ShopifyClient("test-store", "access-token") as client:
        with pytest.raises(ShopUnavailableException):
            await client.graphql(query)


async def test_get_webhook_subscriptions(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["webhookSubscriptions"] = json_fixture("webhook_subscription/list.json")

    async with ShopifyClient("test-store", "access-token") as client:
        subscriptions = await client.get_webhook_subscriptions()

    assert len(subscriptions) == 1
    assert subscriptions[0]["topic"] == ShopifyWebhookTopic.APP_UNINSTALLED


async def test_get_metafield_definitions(
    mock_shopify_api: dict[str, dict[str, Any]],
) -> None:
    mock_shopify_api["metafieldDefinitions"] = json_fixture("metafield/list.json")

    async with ShopifyClient("test-store", "access-token") as client:
        definitions = await client.get_metafield_definitions()

    assert len(definitions) == 1
    assert definitions[0]["namespace"] == "test_namespace"


async def test_create_metafield_definition(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["metafieldDefinitionCreateMutation"] = json_fixture("metafield/create.json")

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.create_metafield_definition(
            {
                "name": "test_name",
                "namespace": "test_namespace",
                "key": "test_key",
                "type": "single_line_text_field",
                "ownerType": "PRODUCT",
            }
        )

    assert response["data"]["metafieldDefinitionCreate"]["createdDefinition"]["name"] == "test_name"


async def test_delete_metafield_definition(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["deleteMetafieldDefinition"] = json_fixture("metafield/delete.json")
    definition_id = "gid://shopify/MetafieldDefinition/1"

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.delete_metafield_definition(definition_id)

    assert response["data"]["metafieldDefinitionDelete"]["deletedDefinitionId"] == definition_id


async def test_check_subscription_status(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["checkAppSubscription"] = json_fixture("subscription/check_subscription.json")

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.check_subscription("1234567890")

    assert response is True


# TODO: Need to fix the test
# async def test_update_redirect_csv(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
#     mock_shopify_api["stagedUploadsCreate"] = json_fixture("staged_upload_create.json")
#     mock_shopify_api["/upload"] = {}
#     async with ShopifyClient("test-store", "access-token") as client:
#         response = await client.upload_redirect_csv(
#             [{"source_url": "https://example.com/1", "target_url": "https://example.com/2"}]
#         )
#     assert type(response) is str


async def test_create_redirects_import(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["urlRedirectImportCreate"] = json_fixture("redirect_import_create.json")
    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.create_redirects_import("https://example.com/redirects.csv")
    assert (
        response
        == json_fixture("redirect_import_create.json")["data"]["urlRedirectImportCreate"]["urlRedirectImport"]["id"]
    )


async def test_submit_redirects_import(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["RedirectImportSubmit"] = json_fixture("redirect_import_submit.json")
    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.submit_redirects_import("gid://shopify/UrlRedirectImport/1")
    assert response == json_fixture("redirect_import_submit.json")["data"]["urlRedirectImportSubmit"]["job"]
