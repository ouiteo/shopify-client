from typing import Any, Literal

from typing_extensions import TypedDict

from shopify_client.builder import ShopifyQuery


class QueryTestCase(TypedDict):
    test_name: str
    entity: str
    fields: list[Any]
    args: dict[str, Any] | None
    query_type: Literal["query", "mutation"]
    expected: str


def test_simple_query() -> None:
    query = ShopifyQuery(operation_name="getProduct", entity="product", fields=["id", "title", "handle"])
    expected = """
    query getProduct {
        product {
            id
            title
            handle
        }
    }
    """
    assert str(query).replace("\n", " ").replace("  ", " ") == expected


def test_query_with_args() -> None:
    query = ShopifyQuery(
        operation_name="getProducts",
        entity="products",
        fields=["id", "title"],
        args={"first": 10, "query": "status:active"},
    )
    expected = """
    query getProducts {
        products(first: 10, query: "status:active") {
            edges {
                node { id title }
            }
        }
    }
    """
    assert str(query).replace("\n", " ").replace("  ", " ") == expected


def test_nested_fields() -> None:
    query = ShopifyQuery(
        operation_name="getOrder",
        entity="order",
        fields=[
            "id",
            {"name": "customer", "fields": ["email", "name"]},
            {"name": "lineItems", "args": {"first": 5}, "fields": ["id", "quantity"]},
        ],
    )
    expected = """
    query getOrder {
        order {
            id
            customer {
                email
                name
            }
            lineItems(first: 5) {
                id
                quantity
            }
        }
    }
    """
    assert str(query).replace("\n", " ").replace("  ", " ") == expected


def test_nested_fields_with_connection() -> None:
    query = ShopifyQuery(operation_name="getOrders", entity="orders", fields=["id", "totalPrice"], args={"first": 10})
    expected = """
    query getOrders {
        orders(first: 10) {
            edges {
                node { id totalPrice }
            }
        }
    }
    """
    assert str(query).replace("\n", " ").replace("  ", " ") == expected


def test_mutation_with_variables() -> None:
    query = ShopifyQuery(
        operation_name="webhookSubscriptionCreate",
        entity="webhookSubscriptionCreate",
        fields=[
            {
                "name": "webhookSubscription",
                "fields": [
                    "id",
                    "topic",
                    "filter",
                    "format",
                    {
                        "name": "endpoint",
                        "fields": ["__typename", {"name": "... on WebhookHttpEndpoint", "fields": ["callbackUrl"]}],
                    },
                ],
            },
            {"name": "userErrors", "fields": ["field", "message"]},
        ],
        args={
            "topic": {"type": "WebhookSubscriptionTopic!", "value": "$topic"},
            "webhookSubscription": {"type": "WebhookSubscriptionInput!", "value": "$webhookSubscription"},
        },
        query_type="mutation",
        variables={
            "topic": {"type": "WebhookSubscriptionTopic!"},
            "webhookSubscription": {"type": "WebhookSubscriptionInput!"},
        },
    )
    expected = """
    mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
        webhookSubscriptionCreate(
            topic: $topic
            webhookSubscription: $webhookSubscription
        ) {
            webhookSubscription {
            id
            topic
            filter
            format
            endpoint {
                __typename
                ... on WebhookHttpEndpoint {
                callbackUrl
                }
            }
            }
            userErrors {
            field
            message
            }
        }
    }
    """  # noqa: E501
    assert str(query).replace("\n", " ").replace("  ", " ") == expected


async def test_get_bulk_operation_by_id() -> None:
    query = ShopifyQuery(
        operation_name="currentBulkOperation",
        entity="currentBulkOperation",
        fields=["id", "status", "errorCode", "createdAt", "completedAt", "objectCount", "fileSize", "url", "partialDataUrl"],
    )
    expected = """
    query currentBulkOperation {
        currentBulkOperation {
            id
            status
            errorCode
            createdAt
            completedAt
            objectCount
            fileSize
            url
            partialDataUrl
        }
    }
    """
    assert str(query).replace("\n", " ").replace("  ", " ") == expected
