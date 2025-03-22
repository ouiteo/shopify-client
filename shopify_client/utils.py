from collections import defaultdict
from typing import Any

from graphql_query import Argument, Field, Fragment, InlineFragment, Operation, Query

Row = dict[str, Any]


def get_error_codes(data: dict[str, Any]) -> set[str]:
    codes = set()
    for error in data.get("errors", []):
        codes.add(error.get("extensions", {}).get("code"))
    if data.get("error"):
        codes.add(data.get("error", {}).get("extensions", {}).get("code"))

    return codes


def create_paginated_query(
    entity: str,
    fields: list[str],
    first: int = 10,
) -> Operation:
    """Create a paginated query for any entity"""
    return Operation(
        type="query",
        name=f"get{entity.capitalize()}",
        queries=[
            Query(
                name=entity,
                arguments=[Argument(name="first", value=first)],
                fields=[
                    *wrap_edges([Field(name=field) for field in fields]),
                    Field(name="pageInfo", fields=["hasNextPage", "endCursor"]),
                ],
            )
        ],
    )


def format_query(query: str) -> str:
    """
    Format a GraphQL query string consistently
    """
    return " ".join([x.strip() for x in query.split("\n")]).strip().replace("( ", "(").replace(" )", ")")


def wrap_edges(fields: list[str | Field | InlineFragment | Fragment]) -> list[str | Field | InlineFragment | Fragment]:
    """Helper function to wrap fields in edges/node structure for connections"""
    return [Field(name="edges", fields=[Field(name="node", fields=fields)])]


def paginated_json_to_entities_dfs(data: list[Row]) -> dict[str, Any]:
    """
    convert data into a dictionary of entities, keyed on entity name,
    ensuring each child entity has its parents id as a __parentId key

    e.g

    client = ShopifyClient("test-store", "test-token")
    query = Operation(
        type="query",
        queries=[
            Query(
                name="products",
                fields=["id", "title", "handle"],
                arguments=[Argument(name="first", value=250)],
            )
        ],
    )
    data = await client.graphql_call_with_pagination(query)
    df = graphql_to_pandas(data)
    """
    import pandas as pd

    datasets = defaultdict(list)
    for item in data:
        item_copy = item.copy()
        parent_entity = item["id"].split("/")[-2]
        for key, value in item.items():
            if isinstance(value, dict) and "edges" in value:
                for edge in value["edges"]:
                    edge["node"]["__parentId"] = item["id"]
                    child_entity = edge["node"]["id"].split("/")[-2]
                    datasets[child_entity].append(edge["node"])
                item_copy.pop(key)
        datasets[parent_entity].append(item_copy)

    return {k: pd.DataFrame(v) for k, v in datasets.items()}


def pd_jsonl_to_entities_dfs(df: Any) -> dict[str, Any]:
    """
    convert a dataframe read from jsonl into a dictionary of entities, keyed on entity name,
    ensuring each child entity has its parents id as a __parentId key, e.g:

    df = pd.read_json("data.jsonl", lines=True)
    datasets = pd_jsonl_to_entities(df)
    """

    datasets = {}
    if "__parentId" in df.columns:
        parent_df = df[df["__parentId"].isna()].dropna(axis=1, how="all")
        parent_entity = parent_df["id"].iloc[0].replace("\\", "").split("/")[-2]
        datasets.update({parent_entity: parent_df})

        child_df = df[~df["__parentId"].isna()].dropna(axis=1, how="all")
        child_df["entity"] = child_df["id"].map(lambda x: x.replace("\\", "").split("/")[-2])
        for entity, iter_child in child_df.groupby("entity"):
            child_df = iter_child.drop("entity", axis=1)
            datasets.update({entity: child_df})
    else:
        parent_entity = df["id"].iloc[0].replace("\\", "").split("/")[-2]
        datasets.update({parent_entity: df})

    return datasets
