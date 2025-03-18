from collections import defaultdict
from typing import Any

Row = dict[str, Any]


def get_error_codes(data: dict[str, Any]) -> set[str]:
    codes = set()
    for error in data.get("errors", []):
        codes.add(error.get("extensions", {}).get("code"))
    if data.get("error"):
        codes.add(data.get("error", {}).get("extensions", {}).get("code"))

    return codes


def graphql_to_pandas(data: list[Row]) -> dict[str, Any]:
    """
    convert data into a dictionary of entities, keyed on entity name,
    ensuring each child entity has its parents id as a __parentId key

    e.g

    client = ShopifyClient("test-store", "test-token")
    query = str(ShopifyQuery("products", ["id", "title", "handle"], args={"first": 250}))
    data = await client.graphql_call_with_pagination("products", "query { products { id, title } }")
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


def normalise_jsonl(df: Any) -> dict[str, Any]:
    """
    normalise jsonl data into a dictionary of entities, keyed on entity name,
    ensuring each child entity has its parents id as a __parentId key
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
