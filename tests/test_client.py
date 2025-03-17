from typing import Any

import jsonlines
import pandas as pd
import pytest

from shopify_client.client import ShopifyClient
from shopify_client.exceptions import QueryError
from shopify_client.types import ShopifyWebhookSubscription, ShopifyWebhookTopic


async def test_basic_graphql_call(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["shopName"] = {"data": {"shop": {"name": "Test Store 1"}}}

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql("query shopName{ shop { name } }")

    assert response == {"data": {"shop": {"name": "Test Store 1"}}}

    # test client with timeout
    async with ShopifyClient("test-store", "access-token", timeout=60.0) as client:
        response = await client.graphql("query shopName{ shop { name } }")

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

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql_call_with_pagination(
            "products",
            """
            query GetProducts{
                products {
                    edges {
                        node {
                            id
                            title
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """,
        )

    assert response == [
        {"id": "1", "title": "Product 1"},
        {"id": "2", "title": "Product 2"},
    ]


async def test_graphql_call_with_unrecoverable_error(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["shopName"] = {
        "error": {
            "data": None,
            "errors": [{"message": "Invalid query syntax"}],
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        with pytest.raises(QueryError) as exc_info:
            await client.graphql("query shopName{ shop { name } }")

    assert "Invalid query syntax" in str(exc_info.value)


async def test_graphql_call_with_error_and_retry(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["shopName"] = {
        "retry": {
            "first": {
                "status_code": 429,  # Too Many Requests
                "data": {"errors": [{"message": "Rate limit exceeded"}]},
            },
            "second": {
                "status_code": 200,
                "data": {"shop": {"name": "Test Store"}},
            },
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.graphql("query shopName{ shop { name } }")

    assert response == {"data": {"shop": {"name": "Test Store"}}}


async def test_poll_until_complete(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api = {
        "running": {
            "data": {
                "currentBulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "RUNNING",
                    "objectCount": 1,
                    "url": "https://download.com",
                }
            }
        },
        "completed": {
            "data": {
                "currentBulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "COMPLETED",
                    "objectCount": 1,
                    "url": "https://download.com",
                }
            }
        },
    }

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.poll_until_complete(
            "gid://shopify/BulkOperation/1",
            "QUERY",
            response_type="jsonlines",
        )

    assert isinstance(response, jsonlines.Reader)


async def test_run_bulk_operation_query(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api = {
        "submit": {
            "data": {
                "bulkOperationRunQuery": {
                    "bulkOperation": {
                        "id": "gid://shopify/BulkOperation/1",
                    },
                    "userErrors": [],
                }
            }
        },
        "running": {
            "data": {
                "currentBulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "RUNNING",
                    "objectCount": 1,
                    "url": "https://download.com",
                }
            }
        },
        "completed": {
            "data": {
                "currentBulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "COMPLETED",
                    "objectCount": 1,
                    "url": "https://download.com",
                }
            }
        },
    }

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.run_bulk_operation_query(
            """
            {
                products {
                    edges {
                        node {
                            id
                            title
                        }
                    }
                }
            }
            """,
            wait=True,
            return_type="jsonlines",
        )

    assert isinstance(response, jsonlines.Reader)


async def test_jsonl_pandas_return(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["BulkOperation"] = {
        "data": {
            "currentBulkOperation": {
                "id": "gid://shopify/BulkOperation/1",
                "status": "COMPLETED",
                "objectCount": 1,
                "url": "https://download.com",
            }
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.poll_until_complete(
            "gid://shopify/BulkOperation/1",
            "QUERY",
            response_type="pandas",
        )

    assert isinstance(response, pd.DataFrame)


async def test_jsonl_jsonlines_return(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["BulkOperation"] = {
        "data": {
            "currentBulkOperation": {
                "id": "gid://shopify/BulkOperation/1",
                "status": "COMPLETED",
                "objectCount": 1,
                "url": "https://download.com",
            }
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.poll_until_complete(
            "gid://shopify/BulkOperation/1",
            "QUERY",
            response_type="jsonlines",
        )

    assert isinstance(response, jsonlines.Reader)


async def test_run_bulk_operation_query_with_error(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["BulkOperation"] = {
        "error": {
            "data": {
                "bulkOperationRunQuery": {
                    "bulkOperation": None,
                    "userErrors": [{"message": "Invalid query syntax"}],
                }
            }
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        with pytest.raises(QueryError) as exc_info:
            await client.run_bulk_operation_query("invalid query")

    assert "Invalid query syntax" in str(exc_info.value)


async def test_run_bulk_operation_mutation(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["BulkOperation"] = {
        "submit": {
            "data": {
                "stagedUploadsCreate": {
                    "userErrors": [],
                    "stagedTargets": [
                        {
                            "url": "https://upload.com",
                            "parameters": [
                                {
                                    "name": "key",
                                    "value": "thing",
                                }
                            ],
                        }
                    ],
                },
                "bulkOperationRunMutation": {
                    "bulkOperation": {
                        "id": "gid://shopify/BulkOperation/1",
                    },
                    "userErrors": [],
                },
            }
        },
        "running": {
            "data": {
                "currentBulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "RUNNING",
                    "objectCount": 1,
                    "url": "https://download.com",
                }
            }
        },
        "completed": {
            "data": {
                "currentBulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "COMPLETED",
                    "objectCount": 1,
                    "url": "https://download.com",
                }
            }
        },
    }

    async with ShopifyClient("test-store", "access-token") as client:
        response = await client.run_bulk_operation_mutation(
            """
            mutation productUpdate($input: ProductInput!) {
                productUpdate(input: $input) {
                    product {
                        id
                        title
                    }
                }
            }
            """,
            [{"title": "Updated Product"}],
            wait=True,
            return_type="jsonlines",
        )

    assert isinstance(response, jsonlines.Reader)


async def test_run_bulk_operation_mutation_with_error(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["BulkOperation"] = {
        "error": {
            "data": {
                "stagedUploadsCreate": {
                    "userErrors": [{"message": "Invalid file format"}],
                    "stagedTargets": [],
                },
                "bulkOperationRunMutation": {
                    "bulkOperation": None,
                    "userErrors": [{"message": "Invalid mutation syntax"}],
                },
            }
        }
    }

    async with ShopifyClient("test-store", "access-token") as client:
        with pytest.raises(ValueError) as exc_info:
            await client.run_bulk_operation_mutation(
                "invalid mutation",
                [{"title": "Updated Product"}],
            )

    assert "Invalid file format" in str(exc_info.value)


async def test_parse_query() -> None:
    query = """
    query {
        shop {
            name
        }
    }
    """
    parsed = ShopifyClient.parse_query(query)
    assert parsed == "query { shop { name } }"


async def test_proxy_pass() -> None:
    mock_shopify_api = {
        "proxy": {
            "status_code": 200,
            "data": {"shop": {"name": "Test Store"}},
        }
    }

    response = await ShopifyClient.proxy_pass(
        "test-store",
        "access-token",
        "GET",
        "admin/api/2024-01/shop.json",
        "",
    )

    assert response.status_code == 200
    assert response.json() == {"shop": {"name": "Test Store"}}


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


async def test_get_permanent_token() -> None:
    mock_shopify_api = {
        "token": {
            "status_code": 200,
            "data": {
                "access_token": "test-access-token",
                "scope": "read_products,write_products",
            },
        }
    }

    access_token, scope = await ShopifyClient.get_permanent_token(
        "test-store",
        "test-code",
        "test-client",
        "test-secret",
    )

    assert access_token == "test-access-token"
    assert scope == "read_products,write_products"


async def test_subscribe_to_topic(mock_shopify_api: dict[str, dict[str, Any]]) -> None:
    mock_shopify_api["webhookSubscribe"] = {
        "subscribe": {
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
    }

    async with ShopifyClient("test-store", "access-token") as client:
        await client.subscribe_to_topic(
            ShopifyWebhookTopic.PRODUCTS_CREATE,
            ShopifyWebhookSubscription(
                arn="arn:aws:events:region:account:event-bus/name",
                format="JSON",
            ),
        )
