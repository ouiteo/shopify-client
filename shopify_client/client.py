import asyncio
import csv
import logging
import uuid
from http import HTTPStatus
from io import BytesIO, StringIO
from types import TracebackType
from typing import Any, Literal, Optional, Self, Type, cast
from urllib.parse import urlencode

import httpx
import jsonlines
from graphql_query import Argument, Field, Operation, Query, Variable
from httpx import AsyncClient as AsyncHttpxClient
from httpx import Response as HttpxResponse
from httpx._types import RequestContent
from tenacity import retry, retry_if_exception_type, wait_exponential

from .exceptions import (
    BulkQueryInProgress,
    QueryError,
    RetriableException,
    ShopUnavailableException,
    ThrottledException,
)
from .types import EventBridgeWebhookSubscriptionInput, ShopifyWebhookTopic, WebhookSubscriptionInput
from .utils import get_error_codes, wrap_edges

logger = logging.getLogger(__name__)

retry_on_status = [
    HTTPStatus.TOO_MANY_REQUESTS.value,
    HTTPStatus.BAD_GATEWAY.value,
    HTTPStatus.SERVICE_UNAVAILABLE.value,
    HTTPStatus.GATEWAY_TIMEOUT.value,
]
shop_unavailable_status = [
    HTTPStatus.PAYMENT_REQUIRED.value,
    HTTPStatus.NOT_FOUND.value,
]


ShopifyResource = Literal[
    "COLLECTION_IMAGE",
    "URL_REDIRECT_IMPORT",
    "orders",
]

MimeType = Literal[
    "text/csv",
    "image/jpeg",
    "image/jpg",
    "image/png",
]

HttpMethod = Literal[
    "PUT",
    "POST",
]


class ShopifyClient:
    def __init__(self, shop_name: str, access_token: str, version: str = "unstable", timeout: float = 5.0) -> None:
        self.shop_name = shop_name
        self.access_token = access_token
        self.base_url = f"https://{shop_name}.myshopify.com/admin/api/{version}/graphql.json"
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Shopify-Access-Token": access_token,
            },
        )

    async def __aenter__(self) -> Self:
        await self.session.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        await self.session.__aexit__(exc_type, exc_value, traceback)

    @staticmethod
    def generate_redirect_url(client_id: str, scopes: list[str], store: str, state: str, redirect_uri: str) -> str:
        return f"https://{store}/admin/oauth/authorize?" + urlencode(
            {
                "client_id": client_id,
                "scope": ",".join(scopes),
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )

    @staticmethod
    async def get_permanent_token(store: str, code: str, client_id: str, secret: str) -> tuple[str, str]:
        """
        Gets a permanent access token for a store
        """
        url = f"https://{store}.myshopify.com/admin/oauth/access_token"
        async with httpx.AsyncClient() as client:
            payload = {
                "code": code,
                "client_id": client_id,
                "client_secret": secret,
            }
            response: httpx.Response = await client.post(url, data=payload)

        response.raise_for_status()
        data = response.json()

        return data["access_token"], data["scope"]

    @staticmethod
    async def proxy_pass(store: str, token: str, method: str, url: str, body: RequestContent) -> httpx.Response:
        """
        Proxy requests directly to the Shopify API.
        """
        base_url = f"https://{store}.myshopify.com/"
        client = httpx.AsyncClient(
            base_url=base_url, headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
        )

        proxy_request = client.build_request(method, url, content=body)
        response = await client.send(proxy_request, stream=True)

        return response

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(RetriableException))
    async def graphql(self, query: Operation, variables: dict[str, Any] = {}) -> dict[str, Any]:
        """
        Execute a GraphQL query against the Shopify API.

        Args:
            query: An Operation instance that defines the query structure
            variables: Variables to pass to the query

        Returns:
            The parsed JSON response from the API

        Raises:
            QueryError: If the query contains errors
            RetriableException: If the request should be retried due to temporary issues
        """
        json_data = {"query": query.render(), "variables": variables}
        response = await self.session.post(self.base_url, json=json_data)
        if response.status_code in retry_on_status:
            raise RetriableException(f"retrying http {response.status_code}")
        elif response.status_code in shop_unavailable_status:
            raise ShopUnavailableException(f"Shop not available : {self.base_url}")
        response.raise_for_status()
        data = cast(dict[str, Any], response.json())

        error_codes = get_error_codes(data)
        if error_codes:
            if "THROTTLED" in error_codes:
                raise ThrottledException(data.get("errors") or data.get("error"))
            raise QueryError(data.get("errors") or data.get("error"))

        return data

    async def graphql_call_with_pagination(  # noqa: C901
        self, query: Operation, variables: dict[str, Any] = {}, max_limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        :child_entity: The child entity to extract. For example, pass "products" to extract from collections.products.
        Execute a GraphQL query with pagination.
        Returns a list of nodes from the response, handling both paginated and non-paginated responses.
        """
        results: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            # Update variables with cursor if we have one
            current_variables = {**variables}
            if cursor is not None:
                current_variables["cursor"] = cursor

            # Make the GraphQL call
            response = await self.graphql(query, current_variables)
            data = response["data"]

            # Find and process nodes from the response
            for value in data.values():
                if isinstance(value, dict):
                    # Parse child entity
                    value = next((val for _, val in value.items() if "pageInfo" in val), value)

                    # Handle paginated response
                    if "edges" in value:
                        results.extend(edge["node"] for edge in value["edges"])
                        if "pageInfo" in value and value["pageInfo"]["hasNextPage"]:
                            cursor = value["pageInfo"]["endCursor"]
                        else:
                            cursor = None
                    # Handle non-paginated response with nodes
                    elif "nodes" in value:
                        results.extend(value["nodes"])
                        cursor = None

            # Check if we've hit the max limit
            if max_limit and len(results) >= max_limit:
                results = results[:max_limit]
                break

            # Break if no more pages
            if cursor is None:
                break

        return results

    async def is_bulk_job_running(self, job_type: str) -> bool:
        """Check if a bulk operation is running"""
        query = Operation(
            type="query",
            name="currentBulkOperation",
            queries=[
                Query(
                    name="currentBulkOperation",
                    arguments=[Argument(name="type", value=job_type)],
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
        response = await self.graphql(query)
        current_bulk_operation = response["data"]["currentBulkOperation"]
        if current_bulk_operation is not None and current_bulk_operation["status"] in ["CREATED", "RUNNING"]:
            return True

        return False

    async def poll_until_complete(self, job_id: str, job_type: str) -> HttpxResponse:
        """Poll the bulk operation until it is complete"""
        query = Operation(
            type="query",
            name="currentBulkOperation",
            queries=[
                Query(
                    name="currentBulkOperation",
                    arguments=[Argument(name="type", value=job_type)],
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
        bulk_check_response = await self.graphql(query)

        current_bulk_operation = bulk_check_response["data"]["currentBulkOperation"]
        if current_bulk_operation is None or current_bulk_operation["id"] != job_id:
            raise ValueError(f"Job {job_id} not found")

        status = current_bulk_operation["status"]
        objectCount = current_bulk_operation["objectCount"]

        if status in ["CREATED", "RUNNING"]:
            logger.debug(f"Job {job_id} {job_type} is {status}, objectCount:{objectCount}, waiting 1 second")
            await asyncio.sleep(1)
            return await self.poll_until_complete(job_id, job_type)

        elif status == "COMPLETED":
            data_url = current_bulk_operation["url"]
            if data_url:
                async with AsyncHttpxClient() as client:
                    download_response = await client.get(data_url)

                download_response.raise_for_status()
                return download_response

            else:  # data url was None, it means job returned no data
                return HttpxResponse(status_code=204, content=b"")

        raise ValueError(f"Job failed with status {status} [{bulk_check_response}]")

    async def run_bulk_operation_query(
        self, sub_query: Query, variables: dict[str, Any] = {}, wait: bool = True
    ) -> str | jsonlines.Reader:
        is_job_running = await self.is_bulk_job_running(job_type="QUERY")
        if is_job_running:
            raise BulkQueryInProgress("Bulk query job already running")

        subquery = '"""\n{\n' + sub_query.render() + '\n}\n"""'
        query = Operation(
            type="mutation",
            name="bulkOperationRunQuery",
            queries=[
                Query(
                    name="bulkOperationRunQuery",
                    arguments=[Argument(name="query", value=subquery)],
                    fields=[
                        Field(name="bulkOperation", fields=[Field(name="id"), Field(name="status")]),
                        Field(name="userErrors", fields=[Field(name="field"), Field(name="message")]),
                    ],
                )
            ],
        )
        response = await self.graphql(query, variables)

        user_errors = response["data"]["bulkOperationRunQuery"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)

        job_id: str = response["data"]["bulkOperationRunQuery"]["bulkOperation"]["id"]
        if wait:
            http_response = await self.poll_until_complete(job_id, "QUERY")
            reader = jsonlines.Reader(BytesIO(http_response.content))
            return reader

        return job_id

    async def run_bulk_operation_mutation(
        self, query: Operation, rows: list[dict[str, Any]], key: str | None = "input", wait: bool = True
    ) -> str | jsonlines.Reader:
        filename = f"{uuid.uuid4()}.jsonl"
        stage_mutation_query = Operation(
            type="mutation",
            name="stagedUploadsCreate",
            variables=[Variable(name="input", type="[StagedUploadInput!]!")],
            queries=[
                Query(
                    name="stagedUploadsCreate",
                    arguments=[
                        Argument(
                            name="input",
                            value="$input",
                        )
                    ],
                    fields=[
                        Field(
                            name="userErrors",
                            fields=[
                                Field(name="message"),
                                Field(name="field"),
                            ],
                        ),
                        Field(
                            name="stagedTargets",
                            fields=[
                                Field(name="url"),
                                Field(name="resourceUrl"),
                                Field(
                                    name="parameters",
                                    fields=[
                                        Field(name="name"),
                                        Field(name="value"),
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        )
        variables = {
            "input": [
                {
                    "resource": "BULK_MUTATION_VARIABLES",
                    "filename": f"{filename}",
                    "mimeType": "text/jsonl",
                    "httpMethod": "POST",
                }
            ]
        }

        ###################
        # Stage Mutations #
        ###################
        # Get the upload parameters for our mutation file
        stage_mutations_response = await self.graphql(stage_mutation_query, variables)
        if not stage_mutations_response.get("data"):
            raise ValueError(stage_mutations_response["errors"])

        stage_mutations_data = stage_mutations_response["data"]["stagedUploadsCreate"]["stagedTargets"][0]
        mutations_upload_url = stage_mutations_data["url"]
        mutations_upload_params = stage_mutations_data["parameters"]

        ####################
        # Upload Mutations #
        ####################
        if key is not None:
            rows = [{key: row} for row in rows]
        fp = BytesIO()
        writer = jsonlines.Writer(fp)
        writer.write_all(rows)
        fp.seek(0)

        files = {"file": (filename, fp, "application/octet-stream")}
        data = {param["name"]: (param["value"],) for param in mutations_upload_params}
        staged_upload_path = data["key"][0]

        async with httpx.AsyncClient() as client:
            mutations_upload_response = await client.post(mutations_upload_url, data=data, files=files)

        mutations_upload_response.raise_for_status()

        ######################
        # Run Bulk Operation #
        ######################

        bulk_mutation_query = Operation(
            type="mutation",
            name="bulkOperationRunMutation",
            queries=[
                Query(
                    name="bulkOperationRunMutation",
                    arguments=[
                        Argument(name="mutation", value=f'"""{query}"""'),
                        Argument(name="stagedUploadPath", value=staged_upload_path),
                    ],
                    fields=[
                        Field(
                            name="bulkOperation",
                            fields=[
                                Field(name="id"),
                                Field(name="url"),
                                Field(name="status"),
                            ],
                        ),
                        Field(
                            name="userErrors",
                            fields=[
                                Field(name="message"),
                                Field(name="field"),
                            ],
                        ),
                    ],
                )
            ],
        )
        response = await self.graphql(bulk_mutation_query)
        if not response.get("data"):
            raise ValueError(response["errors"])

        user_errors = response["data"]["bulkOperationRunMutation"]["userErrors"]
        if user_errors:
            raise ValueError(user_errors)

        job_id: str = response["data"]["bulkOperationRunMutation"]["bulkOperation"]["id"]

        if not wait:
            return job_id

        http_response = await self.poll_until_complete(job_id, "MUTATION")
        reader = jsonlines.Reader(BytesIO(http_response.content))
        return reader

    #########################
    # Webhook Subscriptions #
    #########################
    async def get_webhook_subscriptions(self) -> list[dict[str, Any]]:
        """Get all webhook subscriptions"""
        query = Operation(
            type="query",
            name="webhookSubscriptions",
            queries=[
                Query(
                    name="webhookSubscriptions",
                    arguments=[Argument(name="first", value=250)],
                    fields=wrap_edges(
                        [
                            Field(name="id"),
                            Field(name="topic"),
                            Field(
                                name="endpoint",
                                fields=[
                                    Field(name="... on WebhookHttpEndpoint", fields=[Field(name="callbackUrl")]),
                                    Field(name="... on WebhookEventBridgeEndpoint", fields=[Field(name="arn")]),
                                ],
                            ),
                        ]
                    ),
                )
            ],
        )
        response = await self.graphql(query)
        return [edge["node"] for edge in response["data"]["webhookSubscriptions"]["edges"]]

    async def subscribe_to_topic(self, topic: ShopifyWebhookTopic, subscription: WebhookSubscriptionInput) -> None:
        """Subscribe to a webhook topic"""
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
        response = await self.graphql(
            query,
            variables={
                "topic": topic.value,
                "webhookSubscription": subscription,
            },
        )
        user_errors = response["data"]["webhookSubscriptionCreate"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)

    async def eventbridge_subscribe_to_topic(
        self, topic: ShopifyWebhookTopic, subscription: EventBridgeWebhookSubscriptionInput
    ) -> None:
        """EventBridge webhook subscription topic"""
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

        response = await self.graphql(
            query,
            variables={
                "topic": topic.value,
                "webhookSubscription": subscription,
            },
        )

        user_errors = response["data"]["eventBridgeWebhookSubscriptionCreate"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)

    async def delete_webhook_subscription(self, subscription_id: str) -> None:
        """Delete a webhook subscription"""
        query = Operation(
            type="mutation",
            name="webhookSubscriptionDelete",
            queries=[
                Query(
                    name="webhookSubscriptionDelete",
                    arguments=[Argument(name="id", value="$id")],
                    fields=[
                        Field(name="deletedWebhookSubscriptionId"),
                        Field(
                            name="userErrors",
                            fields=[Field(name="field"), Field(name="message")],
                        ),
                    ],
                )
            ],
            variables=[Variable(name="id", type="ID!")],
        )
        response = await self.graphql(query, variables={"id": subscription_id})
        user_errors = response["data"]["webhookSubscriptionDelete"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)

    #########################
    # Metafield Definitions #
    #########################
    async def get_metafield_definitions(
        self,
        owner_type: Literal["PRODUCT", "COLLECTION"] = "COLLECTION",
        namespace: Optional[str] = None,
        key: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        List metafield definitions for a given owner type, namespace, and key.
        """
        query = Operation(
            type="query",
            name="metafieldDefinitions",
            queries=[
                Query(
                    name="metafieldDefinitions",
                    arguments=[
                        Argument(name="first", value=250),
                        Argument(name="ownerType", value="$ownerType"),
                        *([Argument(name="namespace", value="$namespace")] if namespace else []),
                        *([Argument(name="key", value="$key")] if key else []),
                    ],
                    fields=wrap_edges([Field(name="id"), Field(name="name"), Field(name="namespace")]),
                )
            ],
            variables=[
                Variable(name="ownerType", type="MetafieldOwnerType!"),
                *([Variable(name="namespace", type="String")] if namespace else []),
                *([Variable(name="key", type="String")] if key else []),
            ],
        )

        variables: dict[str, Any] = {"ownerType": owner_type}
        if namespace:
            variables["namespace"] = namespace
        if key:
            variables["key"] = key

        response = await self.graphql(query, variables=variables)
        return [edge["node"] for edge in response["data"]["metafieldDefinitions"]["edges"]]

    async def create_metafield_definition(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Create metafield definition
        """
        query = Operation(
            type="mutation",
            name="metafieldDefinitionCreateMutation",
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

        response = await self.graphql(query, {"input": input})

        user_errors = response.get("data", {}).get("metafieldDefinitionCreate", {}).get("userErrors")
        if user_errors:
            raise ValueError(f"Error creating metafield definition: {user_errors}")

        return response

    async def delete_metafield_definition(
        self, definition_id: str, delete_associated_metafields: bool = True
    ) -> dict[str, Any]:
        """
        Delete a metafield definition
        """
        query = Operation(
            type="mutation",
            name="deleteMetafieldDefinition",
            queries=[
                Query(
                    name="metafieldDefinitionDelete",
                    arguments=[
                        Argument(name="id", value="$id"),
                        Argument(name="deleteAllAssociatedMetafields", value="$deleteAllAssociatedMetafields"),
                    ],
                    fields=[
                        Field(name="deletedDefinitionId"),
                        Field(
                            name="userErrors", fields=[Field(name="field"), Field(name="message"), Field(name="code")]
                        ),
                    ],
                )
            ],
            variables=[
                Variable(name="id", type="ID!"),
                Variable(name="deleteAllAssociatedMetafields", type="Boolean!"),
            ],
        )

        variables = {
            "id": definition_id,
            "deleteAllAssociatedMetafields": delete_associated_metafields,
        }
        response = await self.graphql(query, variables=variables)

        user_errors = response["data"]["metafieldDefinitionDelete"]["userErrors"]
        if user_errors:
            raise ValueError(f"Error deleting metafield definition: {user_errors}")

        return response

    #########################
    # Billing Subscription  #
    #########################
    async def check_subscription(self, id: str) -> bool:
        """
        Check if the subscription is active
        """
        query = Operation(
            type="query",
            name="checkAppSubscription",
            queries=[
                Query(
                    name="node",
                    arguments=[Argument(name="id", value="$id")],
                    fields=[
                        Field(
                            name="... on AppSubscription",
                            fields=[
                                Field(name="id"),
                                Field(name="status"),
                            ],
                        ),
                    ],
                )
            ],
            variables=[Variable(name="id", type="ID!")],
        )

        variables = {"id": f"gid://shopify/AppSubscription/{id}"}
        response = await self.graphql(query, variables)

        node = response.get("data", {}).get("node", None)
        if not node:
            logger.error("Subscription not found")
            return False

        charge_active = node.get("status", "")
        return bool(charge_active and charge_active == "ACTIVE")

    async def upload_redirect_csv(self, rows: list[dict[str, Any]]) -> str:
        filename = f"{uuid.uuid4()}.csv"
        query = Operation(
            type="mutation",
            name="stagedUploadsCreate",
            variables=[Variable(name="input", type="[StagedUploadInput!]!")],
            queries=[
                Query(
                    name="stagedUploadsCreate",
                    arguments=[
                        Argument(
                            name="input",
                            value="",
                        )
                    ],
                    fields=[
                        Field(
                            name="userErrors",
                            fields=[
                                Field(name="message"),
                                Field(name="field"),
                            ],
                        ),
                        Field(
                            name="stagedTargets",
                            fields=[
                                Field(name="url"),
                                Field(
                                    name="parameters",
                                    fields=[
                                        Field(name="name"),
                                        Field(name="value"),
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        )
        variables = {
            "input": [
                {"resource": "URL_REDIRECT_IMPORT", "filename": filename, "mimeType": "text/csv", "httpMethod": "POST"}
            ]
        }
        stage_mutations_response = await self.graphql(query, variables)

        if not stage_mutations_response.get("data"):
            raise ValueError(stage_mutations_response.get("errors"))

        stage_mutations_data: dict[str, Any] = stage_mutations_response["data"]["stagedUploadsCreate"]["stagedTargets"][
            0
        ]
        mutations_upload_url: str = stage_mutations_data["url"]
        mutations_upload_params = stage_mutations_data["parameters"]

        string_fp = StringIO()
        writer = csv.writer(string_fp)

        writer.writerow(["Redirect from", "Redirect to"])
        for row in rows:
            writer.writerow([row["source_url"], row["target_url"]])
        csv_content = string_fp.getvalue()
        fp = BytesIO(csv_content.encode("utf-8"))
        fp.seek(0)

        files = {"file": (filename, fp, "application/octet-stream")}
        data = {param["name"]: (param["value"],) for param in mutations_upload_params}
        staged_upload_path = data["key"][0]

        async with httpx.AsyncClient() as client:
            mutations_upload_response = await client.post(mutations_upload_url, data=data, files=files)

        mutations_upload_response.raise_for_status()

        return str(mutations_upload_url + staged_upload_path)

    async def create_redirects_import(self, url: str) -> str:
        query = query = Operation(
            type="mutation",
            name="urlRedirectImportCreate",
            variables=[Variable(name="url", type="URL!")],
            queries=[
                Query(
                    name="urlRedirectImportCreate",
                    arguments=[
                        Argument(
                            name="url",
                            value="$url",
                        )
                    ],
                    fields=[
                        Field(name="urlRedirectImport", fields=[Field(name="id")]),
                        Field(
                            name="userErrors",
                            fields=[
                                Field(name="message"),
                                Field(name="field"),
                            ],
                        ),
                    ],
                )
            ],
        )
        response = await self.graphql(query, variables={"url": url})
        if not response.get("data"):
            raise ValueError(response.get("errors"))

        user_errors = response["data"]["urlRedirectImportCreate"]["userErrors"]
        if user_errors:
            raise ValueError(user_errors)

        import_id: str = response["data"]["urlRedirectImportCreate"]["urlRedirectImport"]["id"]
        return import_id

    async def submit_redirects_import(self, import_id: str) -> dict[str, Any]:
        query = Operation(
            type="mutation",
            name="RedirectImportSubmit",
            variables=[Variable(name="id", type="ID!")],
            queries=[
                Query(
                    name="urlRedirectImportSubmit",
                    arguments=[
                        Argument(
                            name="id",
                            value="$id",
                        )
                    ],
                    fields=[
                        Field(name="job", fields=[Field(name="id"), Field(name="done")]),
                        Field(
                            name="userErrors",
                            fields=[
                                Field(name="message"),
                                Field(name="field"),
                            ],
                        ),
                    ],
                )
            ],
        )
        response = await self.graphql(query, {"id": import_id})
        if not response.get("data"):
            raise ValueError(response.get("errors"))

        user_errors = response["data"]["urlRedirectImportSubmit"]["userErrors"]
        if user_errors:
            raise ValueError(user_errors)

        job: dict[str, Any] = response["data"]["urlRedirectImportSubmit"]["job"]
        return job
