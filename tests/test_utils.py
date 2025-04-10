from typing import Any

import pandas as pd
import pytest
from graphql_query import Field

from shopify_client.types import FieldsT
from shopify_client.utils import (
    add_to_edges,
    create_paginated_query,
    format_query,
    get_error_codes,
    paginated_json_to_entities_dfs,
    pd_jsonl_to_entities_dfs,
)


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


def test_add_to_edges() -> None:
    fields: FieldsT = [Field(name="id"), Field(name="title")]

    assert add_to_edges(fields) == [
        Field(name="edges", fields=[Field(name="node", fields=fields)]),
    ]


def test_paginated_json_to_entities_dfs() -> None:
    # Sample data with parent-child relationship
    data = [
        {
            "id": "gid://shopify/Product/123",
            "title": "Test Product",
            "variants": {
                "edges": [
                    {"node": {"id": "gid://shopify/ProductVariant/456", "title": "Default Title", "price": "10.00"}},
                    {"node": {"id": "gid://shopify/ProductVariant/789", "title": "Large", "price": "15.00"}},
                ]
            },
        },
        {
            "id": "gid://shopify/Product/456",
            "title": "Another Product",
            "variants": {
                "edges": [
                    {"node": {"id": "gid://shopify/ProductVariant/101", "title": "Default Title", "price": "20.00"}}
                ]
            },
        },
    ]

    # Call the function
    result = paginated_json_to_entities_dfs(data)

    # Check that we have two entity types
    assert set(result.keys()) == {"Product", "ProductVariant"}

    # Check Product entities
    product_df = result["Product"]
    assert isinstance(product_df, pd.DataFrame)
    assert len(product_df) == 2
    assert list(product_df.columns) == ["id", "title"]
    assert product_df.iloc[0]["id"] == "gid://shopify/Product/123"
    assert product_df.iloc[0]["title"] == "Test Product"
    assert product_df.iloc[1]["id"] == "gid://shopify/Product/456"
    assert product_df.iloc[1]["title"] == "Another Product"

    # Check ProductVariant entities
    variant_df = result["ProductVariant"]
    assert isinstance(variant_df, pd.DataFrame)
    assert len(variant_df) == 3
    assert "__parentId" in variant_df.columns
    assert list(variant_df.columns) == ["id", "title", "price", "__parentId"]

    # Check that parent IDs are correctly set
    assert variant_df.iloc[0]["__parentId"] == "gid://shopify/Product/123"
    assert variant_df.iloc[1]["__parentId"] == "gid://shopify/Product/123"
    assert variant_df.iloc[2]["__parentId"] == "gid://shopify/Product/456"


def test_pd_jsonl_to_entities_dfs_with_parent() -> None:
    """Test pd_jsonl_to_entities_dfs with parent-child relationships"""
    # Create a sample DataFrame that mimics data from a JSONL file with parent-child relationship
    data = pd.DataFrame(
        [
            {"id": "gid://shopify/Product/123", "title": "Test Product", "price": "10.00", "__parentId": None},
            {
                "id": "gid://shopify/ProductVariant/456",
                "title": "Default Title",
                "price": "10.00",
                "__parentId": "gid://shopify/Product/123",
            },
            {
                "id": "gid://shopify/ProductVariant/789",
                "title": "Large",
                "price": "15.00",
                "__parentId": "gid://shopify/Product/123",
            },
            {"id": "gid://shopify/Product/456", "title": "Another Product", "price": "20.00", "__parentId": None},
            {
                "id": "gid://shopify/ProductVariant/101",
                "title": "Default Title",
                "price": "20.00",
                "__parentId": "gid://shopify/Product/456",
            },
        ]
    )

    # Call the function with the DataFrame that has __parentId
    result = pd_jsonl_to_entities_dfs(data)

    # Check that we have two entity types
    assert set(result.keys()) == {"Product", "ProductVariant"}

    # Check Product entities
    product_df = result["Product"]
    assert isinstance(product_df, pd.DataFrame)
    assert len(product_df) == 2
    assert list(product_df.columns) == ["id", "title", "price"]
    assert product_df.iloc[0]["id"] == "gid://shopify/Product/123"
    assert product_df.iloc[0]["title"] == "Test Product"
    assert product_df.iloc[1]["id"] == "gid://shopify/Product/456"
    assert product_df.iloc[1]["title"] == "Another Product"

    # Check ProductVariant entities
    variant_df = result["ProductVariant"]
    assert isinstance(variant_df, pd.DataFrame)
    assert len(variant_df) == 3
    assert "__parentId" in variant_df.columns
    assert list(variant_df.columns) == ["id", "title", "price", "__parentId"]

    # Check that parent IDs are correctly set
    assert variant_df.iloc[0]["__parentId"] == "gid://shopify/Product/123"
    assert variant_df.iloc[1]["__parentId"] == "gid://shopify/Product/123"
    assert variant_df.iloc[2]["__parentId"] == "gid://shopify/Product/456"


def test_pd_jsonl_to_entities_dfs_without_parent() -> None:
    """Test pd_jsonl_to_entities_dfs with single entity type (no parent-child relationship)"""
    # Create a sample DataFrame that mimics data from a JSONL file without parent-child relationship
    data_without_parent = pd.DataFrame(
        [
            {"id": "gid://shopify/Product/123", "title": "Test Product", "price": "10.00"},
            {"id": "gid://shopify/Product/456", "title": "Another Product", "price": "20.00"},
        ]
    )

    # Call the function with the DataFrame that doesn't have __parentId
    result = pd_jsonl_to_entities_dfs(data_without_parent)

    # Check that we have one entity type
    assert set(result.keys()) == {"Product"}

    # Check Product entities
    product_df = result["Product"]
    assert isinstance(product_df, pd.DataFrame)
    assert len(product_df) == 2
    assert list(product_df.columns) == ["id", "title", "price"]
    assert product_df.iloc[0]["id"] == "gid://shopify/Product/123"
    assert product_df.iloc[0]["title"] == "Test Product"
    assert product_df.iloc[1]["id"] == "gid://shopify/Product/456"
    assert product_df.iloc[1]["title"] == "Another Product"


def test_create_paginated_query() -> None:
    operation = create_paginated_query("products", ["id", "title"], query_params='"updated_at:>2024-01-01"')
    expected = """
        query getProduct {
            products(
                first: 10
                query: "updated_at:>2024-01-01"
            ) {
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
    """
    assert format_query(operation.render()) == format_query(expected)
