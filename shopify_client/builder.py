import logging
from typing import Any, Literal, Optional, Union

from graphql_query import Argument, Field, Fragment, InlineFragment, Operation, Query

logger = logging.getLogger(__name__)


class ShopifyQuery:
    """
    Helper class to build Shopify GraphQL queries.

    Examples:
        >>> # Simple query
        >>> query = ShopifyQuery("product", ["id", "title", "handle"])
        >>> print(query)

        >>> # Query with pagination and filter
        >>> ShopifyQuery(
        ...     "orders",
        ...     ["id", "totalPrice"],
        ...     args={"first": 100, "query": "status:open"}
        ... )
        >>> print(query)

        >>> # Query with nested fields and arguments
        >>> ShopifyQuery(
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
        ... )
        >>> print(query)
    """

    def __init__(
        self,
        operation_name: str,
        entity: str,
        fields: list[Union[str, dict[str, Any]]],
        args: dict[str, Any] | None = None,
        query_type: Literal["query", "mutation"] = "query",
        variables: Optional[dict[str, dict[str, str]]] = None,
    ) -> None:
        """
        Build a Shopify GraphQL query.

        Args:
            operation_name: Name of the operation (required)
            entity: The Shopify entity to query (e.g., "orders", "product")
            fields: List of fields to request. Can be simple strings or nested field objects.
                   For nested fields, use a dict with 'name', 'fields', and optional 'args' keys.
            args: Arguments to pass to the top-level query
            query_type: Type of query ("query" or "mutation")
            variables: Variable definitions in the format:
                      {"variableName": {"type": "Type!", "value": "$variableName"}}

        Examples:
            >>> # Simple named query
            >>> query = ShopifyQuery(
            ...     "getProduct",
            ...     "product",
            ...     ["id", "title", "handle"]
            ... )

            >>> # Named mutation with variables
            >>> mutation = ShopifyQuery(
            ...     "createWebhook",
            ...     "webhookSubscriptionCreate",
            ...     [...],
            ...     args={"topic": "$topic"},
            ...     query_type="mutation",
            ...     variables={"topic": {"type": "WebhookSubscriptionTopic!"}}
            ... )
        """
        self.operation_name = operation_name
        self.entity = entity
        self.fields = fields
        self.args = args
        self.query_type = query_type
        self.variables = variables

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
        nested_fields = [ShopifyQuery._build_field(f) for f in field.get("fields", [])]

        # Add arguments if present
        args = [Argument(name=key, value=value) for key, value in field.get("args", {}).items()]

        # If field name is plural, wrap nested fields in connection structure
        if field_name.endswith("s") and nested_fields and field_name != "userErrors":
            nested_fields = [ShopifyQuery._wrap_in_connection(nested_fields)]

        return Field(name=field_name, arguments=args, fields=nested_fields if nested_fields else [])

    def _format_variable_definitions(self) -> str:
        """Format variable definitions for the query"""
        if not self.variables:
            return ""

        var_defs = [f"${name}: {details['type']}" for name, details in self.variables.items()]
        return f"({', '.join(var_defs)})"

    def __repr__(self) -> str:
        return f"""ShopifyQuery(
            entity={self.entity},
            fields={self.fields},
            args={self.args},
            query_type={self.query_type},
            operation_name={self.operation_name},
            variables={self.variables}
        )"""

    def __str__(self) -> str:
        """
        Return the rendered GraphQL query string
        """
        # Process all fields
        processed_fields = [self._build_field(field) for field in self.fields]

        # Add arguments for the entity
        entity_args = []
        if self.args:
            entity_args = [Argument(name=key, value=value.get("value", value)) for key, value in self.args.items()]

        # Wrap in connection structure if it's a plural entity
        if self.entity.endswith("s"):
            processed_fields = [self._wrap_in_connection(processed_fields)]

        # Build the query
        operation = Operation(
            type=self.query_type,
            name=self.operation_name,
            queries=[Query(name=self.entity, arguments=entity_args, fields=processed_fields)],
        )

        # Add variable definitions if present
        query_str = operation.render()
        if self.variables:
            # Insert variable definitions after operation name
            operation_start = f"{self.query_type} {self.operation_name or ''}"
            var_defs = self._format_variable_definitions()
            query_str = query_str.replace(operation_start, f"{operation_start}{var_defs}", 1)

        return query_str
