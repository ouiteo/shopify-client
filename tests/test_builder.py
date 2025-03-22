from graphql_query import Argument, Field, Operation, Query, Variable

from shopify_client.utils import format_query, wrap_edges


def test_simple_query() -> None:
    query = Operation(
        type="query",
        name="getProduct",
        queries=[Query(name="product", fields=[Field(name="id"), Field(name="title"), Field(name="handle")])],
    )
    expected = """
    query getProduct {
        product {
            id
            title
            handle
        }
    }
    """
    assert format_query(query.render()) == format_query(expected)


def test_query_with_args() -> None:
    query = Operation(
        type="query",
        name="getProducts",
        queries=[
            Query(
                name="products",
                arguments=[Argument(name="first", value=10), Argument(name="query", value="status:active")],
                fields=wrap_edges([Field(name="id"), Field(name="title")]),
            )
        ],
    )
    expected = """
    query getProducts {
        products(first: 10 query: status:active) {
            edges {
                node {
                    id
                    title
                }
            }
        }
    }
    """
    assert format_query(query.render()) == format_query(expected)


def test_nested_fields() -> None:
    query = Operation(
        type="query",
        name="getOrder",
        queries=[
            Query(
                name="order",
                fields=[
                    Field(name="id"),
                    Field(name="customer", fields=[Field(name="email"), Field(name="name")]),
                    Field(
                        name="lineItems",
                        arguments=[Argument(name="first", value=5)],
                        fields=[Field(name="id"), Field(name="quantity")],
                    ),
                ],
            )
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
    assert format_query(query.render()) == format_query(expected)


def test_nested_fields_with_connection() -> None:
    query = Operation(
        type="query",
        name="getOrders",
        queries=[
            Query(
                name="orders",
                arguments=[Argument(name="first", value=10)],
                fields=wrap_edges([Field(name="id"), Field(name="totalPrice")]),
            )
        ],
    )
    expected = """
    query getOrders {
        orders(first: 10) {
            edges {
                node {
                    id
                    totalPrice
                }
            }
        }
    }
    """
    assert format_query(query.render()) == format_query(expected)


def test_mutation_with_variables() -> None:
    query = Operation(
        type="mutation",
        name="webhookSubscriptionCreate",
        queries=[
            Query(
                name="webhookSubscriptionCreate",
                arguments=[
                    Argument(name="topic", value="$topic"),
                    Argument(name="webhookSubscription", value="$webhookSubscription"),
                ],
                fields=[
                    Field(
                        name="webhookSubscription",
                        fields=[
                            Field(name="id"),
                            Field(name="topic"),
                            Field(name="filter"),
                            Field(name="format"),
                            Field(
                                name="endpoint",
                                fields=[
                                    Field(name="__typename"),
                                    Field(name="... on WebhookEventBridgeEndpoint", fields=[Field(name="arn")]),
                                ],
                            ),
                        ],
                    ),
                    Field(name="userErrors", fields=[Field(name="field"), Field(name="message")]),
                ],
            )
        ],
        variables=[
            Variable(name="topic", type="WebhookSubscriptionTopic!"),
            Variable(name="webhookSubscription", type="WebhookSubscriptionInput!"),
        ],
    )
    expected = """
    mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic! $webhookSubscription: WebhookSubscriptionInput!) {
        webhookSubscriptionCreate(topic: $topic webhookSubscription: $webhookSubscription) {
            webhookSubscription {
                id
                topic
                filter
                format
                endpoint {
                    __typename
                    ... on WebhookEventBridgeEndpoint {
                        arn
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
    assert format_query(query.render()) == format_query(expected)


def test_get_bulk_operation_by_id() -> None:
    query = Operation(
        type="query",
        name="currentBulkOperation",
        queries=[
            Query(
                name="currentBulkOperation",
                fields=[
                    Field(name="id"),
                    Field(name="status"),
                    Field(name="errorCode"),
                    Field(name="createdAt"),
                    Field(name="completedAt"),
                    Field(name="objectCount"),
                    Field(name="fileSize"),
                    Field(name="url"),
                    Field(name="partialDataUrl"),
                ],
            )
        ],
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
    assert format_query(query.render()) == format_query(expected)
