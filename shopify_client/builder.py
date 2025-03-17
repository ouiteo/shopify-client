import logging
from typing import Any, Literal, Union

from graphql_query import Argument, Field, Fragment, InlineFragment, Operation, Query

logger = logging.getLogger(__name__)


class ShopifyQueryBuilder:
    """
    Helper class to build Shopify GraphQL queries.

    Examples:
        >>> # Simple query
        >>> str(ShopifyQueryBuilder("product", ["id", "title", "handle"]))

        >>> # Query with pagination and filter
        >>> str(ShopifyQueryBuilder(
        ...     "orders",
        ...     ["id", "totalPrice"],
        ...     args={"first": 100, "query": "status:open"}
        ... ))

        >>> # Query with nested fields and arguments
        >>> str(ShopifyQueryBuilder(
        ...     "orders",
        ...     [
        ...         "id",
        ...         {
        ...             "name": "customer",
        ...             "fields": ["email", "displayName"]
        ...         },
        ...         {
        ...             "name": "lineItems",
        ...             "args": {"first": 5},
        ...             "fields": ["id", "quantity"]
        ...         }
        ...     ],
        ...     args={"first": 50}
        ... ))
    """

    def __init__(
        self,
        entity: str,
        fields: list[Union[str, dict[str, Any]]],
        *,
        args: dict[str, Any] | None = None,
        query_type: Literal["query", "mutation"] = "query",
    ) -> None:
        """
        Build a Shopify GraphQL query.

        Args:
            entity: The Shopify entity to query (e.g., "orders", "product")
            fields: List of fields to request. Can be simple strings or nested field objects.
                   For nested fields, use a dict with 'name', 'fields', and optional 'args' keys.
            args: Arguments to pass to the top-level query (e.g., {"first": 100, "query": "status:open"})
            query_type: Type of query ("query" or "mutation")
        """
        # Process all fields
        processed_fields = [self._build_field(field) for field in fields]

        # Add arguments for the entity
        entity_args = [Argument(name=key, value=value) for key, value in (args or {}).items()]

        # Wrap in connection structure if it's a plural entity
        if entity.endswith("s"):
            processed_fields = [self._wrap_in_connection(processed_fields)]

        # Build the query
        self._operation = Operation(
            type=query_type,
            queries=[Query(name=entity, arguments=entity_args, fields=processed_fields)],
        )

    @staticmethod
    def _wrap_in_connection(fields: list[str | Field | InlineFragment | Fragment]) -> Field:
        """Wrap fields in edges/node structure for connections"""
        return Field(name="edges", fields=[Field(name="node", fields=fields)])

    @staticmethod
    def _build_field(field: Union[str, dict[str, Any]]) -> str | Field | InlineFragment | Fragment:
        """Build a single field or nested field structure"""
        if isinstance(field, str):
            return Field(name=field)

        field_name = field["name"]
        nested_fields = [ShopifyQueryBuilder._build_field(f) for f in field.get("fields", [])]

        # Add arguments if present
        args = [Argument(name=key, value=value) for key, value in field.get("args", {}).items()]

        # If field name is plural, wrap nested fields in connection structure
        if field_name.endswith("s") and nested_fields:
            nested_fields = [ShopifyQueryBuilder._wrap_in_connection(nested_fields)]

        return Field(name=field_name, arguments=args, fields=nested_fields if nested_fields else [])

    def __str__(self) -> str:
        """Return the rendered GraphQL query string"""
        return self._operation.render()
