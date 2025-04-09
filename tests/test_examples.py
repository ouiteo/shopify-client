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


def test_product_update() -> None:
    query = Operation(
        type="mutation",
        name="productUpdate",
        queries=[
            Query(
                name="productUpdate",
                arguments=[Argument(name="input", value="$input")],
                fields=[
                    Field(name="product", fields=[Field(name="id")]),
                    Field(name="userErrors", fields=[Field(name="field"), Field(name="message")]),
                ],
            )
        ],
        variables=[Variable(name="input", type="ProductInput!")],
    )
    expected = """
    mutation productUpdate($input: ProductInput!) {
        productUpdate(input: $input) {
            product {
                id
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    assert format_query(query.render()) == format_query(expected)


#########################
# Webhook Subscriptions #
#########################
def test_webhook_subscription_create() -> None:
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
                                    Field(name="... on WebhookHttpEndpoint", fields=[Field(name="callbackUrl")]),
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
    assert format_query(query.render()) == format_query(expected)


def test_eventbridge_webhook_subscription_create() -> None:
    query = Operation(
        type="mutation",
        name="eventBridgeWebhookSubscriptionCreate",
        queries=[
            Query(
                name="eventBridgeWebhookSubscriptionCreate",
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
            Variable(name="webhookSubscription", type="EventBridgeWebhookSubscriptionInput!"),
        ],
    )
    exptected = """
    mutation eventBridgeWebhookSubscriptionCreate($topic: WebhookSubscriptionTopic! $webhookSubscription: EventBridgeWebhookSubscriptionInput!) {
        eventBridgeWebhookSubscriptionCreate(topic: $topic webhookSubscription: $webhookSubscription) {
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

    assert format_query(query.render()) == format_query(exptected)


async def test_delete_webhook_subscription() -> None:
    query = Operation(
        type="mutation",
        name="webhookSubscriptionDelete",
        queries=[
            Query(
                name="webhookSubscriptionDelete",
                arguments=[Argument(name="id", value="$id")],
                fields=[
                    Field(name="deletedWebhookSubscriptionId"),
                    Field(name="userErrors", fields=[Field(name="field"), Field(name="message")]),
                ],
            )
        ],
        variables=[
            Variable(name="id", type="ID!"),
        ],
    )

    expected = """
    mutation webhookSubscriptionDelete($id: ID!) {
        webhookSubscriptionDelete(id: $id) {
            deletedWebhookSubscriptionId
            userErrors {
                field
                message
            }
        }
    }
    """

    assert format_query(query.render()) == format_query(expected)


#########################
# Metafield Definitions #
#########################
def test_metafield_definations() -> None:
    query = Operation(
        type="query",
        name="metafieldDefinitions",
        queries=[
            Query(
                name="metafieldDefinitions",
                arguments=[
                    Argument(name="first", value=250),
                    Argument(name="ownerType", value="COLLECTION"),
                    Argument(name="namespace", value="ouiteo"),
                    Argument(name="key", value="collection"),
                ],
                fields=wrap_edges([Field(name="id"), Field(name="name"), Field(name="namespace")]),
            )
        ],
    )
    expected = """
    query metafieldDefinitions {
        metafieldDefinitions(first: 250 ownerType: COLLECTION namespace: ouiteo key: collection) {
            edges {
                node {
                    id
                    name
                    namespace
                }
            }
        }
    }
    """
    assert format_query(query.render()) == format_query(expected)


def test_metafield_defination_create() -> None:
    query = Operation(
        type="mutation",
        name="MetafieldDefinitionCreateMutation",
        queries=[
            Query(
                name="metafieldDefinitionCreate",
                arguments=[Argument(name="definition", value="$input")],
                fields=[
                    Field(
                        name="userErrors",
                        fields=[
                            Field(name="code"),
                            Field(name="message"),
                            Field(name="field"),
                            Field(name="__typename"),
                        ],
                    ),
                    Field(name="__typename"),
                ],
            )
        ],
        variables=[Variable(name="input", type="MetafieldDefinitionInput!")],
    )
    expected = """
    mutation MetafieldDefinitionCreateMutation($input: MetafieldDefinitionInput!) {
        metafieldDefinitionCreate(definition: $input) {
            userErrors {
            code
            message
            field
                __typename
            }
            __typename
        }
    }
    """
    assert format_query(query.render()) == format_query(expected)


def test_metafield_defination_delete() -> None:
    query = Operation(
        type="mutation",
        name="DeleteMetafieldDefinition",
        queries=[
            Query(
                name="metafieldDefinitionDelete",
                arguments=[
                    Argument(name="id", value="$id"),
                    Argument(name="deleteAllAssociatedMetafields", value="$deleteAllAssociatedMetafields"),
                ],
                fields=[
                    Field(name="deletedDefinitionId"),
                    Field(name="userErrors", fields=[Field(name="field"), Field(name="message"), Field(name="code")]),
                ],
            )
        ],
        variables=[
            Variable(name="id", type="ID!"),
            Variable(name="deleteAllAssociatedMetafields", type="Boolean!"),
        ],
    )
    exptected = """
        mutation DeleteMetafieldDefinition($id: ID! $deleteAllAssociatedMetafields: Boolean!) {
        metafieldDefinitionDelete(id: $id deleteAllAssociatedMetafields: $deleteAllAssociatedMetafields) {
            deletedDefinitionId
            userErrors {
                field
                message
                code
            }
        }
    }
    """
    assert format_query(query.render()) == format_query(exptected)


def test_metafield_set() -> None:
    query = Operation(
        type="mutation",
        name="MetafieldsSet",
        queries=[
            Query(
                name="metafieldsSet",
                arguments=[Argument(name="metafields", value="$metafields")],
                fields=[
                    Field(
                        name="metafields",
                        fields=[
                            Field(name="key"),
                            Field(name="namespace"),
                            Field(name="value"),
                            Field(name="createdAt"),
                            Field(name="updatedAt"),
                            Field(
                                name="owner",
                                fields=[
                                    Field(name="... on Product", fields=[Field(name="id"), Field(name="tags")]),
                                ],
                            ),
                        ],
                    ),
                    Field(
                        name="userErrors",
                        fields=[
                            Field(name="field"),
                            Field(name="message"),
                            Field(name="code"),
                        ],
                    ),
                ],
            )
        ],
        variables=[Variable(name="metafields", type="[MetafieldsSetInput!]!")],
    )
    expected = """
    mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
            metafields {
            key
            namespace
            value
            createdAt
            updatedAt
            owner {
                ... on Product {
                    id
                    tags
                }
            }
            }
            userErrors {
                field
                message
                code
            }
        }
    }
    """
    assert format_query(query.render()) == format_query(expected)


def test_get_bulk_operation_by_id() -> None:
    query = Operation(
        type="query",
        name="getBulkOperation",
        queries=[
            Query(
                name="node",
                arguments=[Argument(name="id", value="$id")],
                fields=[
                    Field(
                        name="... on BulkOperation",
                        fields=[
                            Field(name="id"),
                            Field(name="type"),
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
        ],
        variables=[Variable(name="id", type="ID!")],
    )
    expected = """
    query getBulkOperation($id: ID!) {
        node(id: $id) {
            ... on BulkOperation {
                id
                type
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
    }
    """

    assert format_query(query.render()) == format_query(expected)


def test_products_by_collection_id() -> None:
    query = Operation(
        type="query",
        name="GetProductsByCollectionId",
        queries=[
            Query(
                name="collection",
                arguments=[Argument(name="id", value="$collectionId")],
                fields=[
                    Field(
                        name="products",
                        arguments=[Argument(name="first", value=250), Argument(name="after", value="$cursor")],
                        fields=[
                            *wrap_edges([Field(name="id"), Field(name="title")]),
                            Field(name="pageInfo", fields=["hasNextPage", "endCursor"]),
                        ],
                    )
                ],
            )
        ],
        variables=[
            Variable(name="cursor", type="String"),
            Variable(name="collectionId", type="ID!"),
        ],
    )
    expected = """
    query GetProductsByCollectionId($cursor: String $collectionId: ID!) {
        collection(id: $collectionId) {
            products(first: 250 after: $cursor) {
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
    }
    """
    assert format_query(query.render()) == format_query(expected)
