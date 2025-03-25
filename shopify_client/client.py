import asyncio
import logging
from http import HTTPStatus
from types import TracebackType
from typing import Any, Optional, Self, Type, cast
from urllib.parse import urlencode

import httpx
from graphql_query import Argument, Field, Operation, Query, Variable
from httpx._types import RequestContent
from tenacity import retry, retry_if_exception_type, wait_exponential

from .exceptions import (
    BulkQueryInProgress,
    QueryError,
    RetriableException,
    ShopUnavailableException,
    ThrottledException,
)
from .types import ShopifyWebhookTopic, WebhookSubscriptionInput
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
        Execute a GraphQL query with pagination.
        Returns a list of nodes from the response, handling both paginated and non-paginated responses.
        """
        results: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            # Update variables with cursor if we have one
            current_variables = {**variables}
            if cursor is not None:
                current_variables["after"] = cursor

            # Make the GraphQL call
            response = await self.graphql(query, current_variables)
            data = response["data"]

            # Find and process nodes from the response
            for value in data.values():
                if isinstance(value, dict):
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

    async def poll_until_complete(self, job_id: str, job_type: str) -> str | None:
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
            return cast(str | None, current_bulk_operation["url"])

        raise ValueError(f"Job failed with status {status} [{bulk_check_response}]")

    async def run_bulk_operation_query(
        self, sub_query: Query, variables: dict[str, Any] = {}, wait: bool = True
    ) -> str | None:
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
            return await self.poll_until_complete(job_id, "QUERY")

        return job_id

    async def run_bulk_operation_mutation(
        self, sub_query: Operation, variables: dict[str, Any] = {}, wait: bool = True
    ) -> str | None:
        is_job_running = await self.is_bulk_job_running(job_type="MUTATION")
        if is_job_running:
            raise ValueError("Bulk mutation job already running")

        query = Operation(
            type="mutation",
            name="bulkOperationRunMutation",
            queries=[
                Query(
                    name="bulkOperationRunMutation",
                    arguments=[Argument(name="mutation", value=sub_query.render())],
                    fields=[
                        Field(name="bulkOperation", fields=[Field(name="id"), Field(name="status")]),
                        Field(name="userErrors", fields=[Field(name="field"), Field(name="message")]),
                    ],
                )
            ],
        )
        response = await self.graphql(query, variables)

        user_errors = response["data"]["bulkOperationRunMutation"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)

        job_id: str = response["data"]["bulkOperationRunMutation"]["bulkOperation"]["id"]
        if wait:
            return await self.poll_until_complete(job_id, "MUTATION")

        return job_id

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
                                        Field(name="... on WebhookEventBridgeEndpoint", fields=[Field(name="arn")]),
                                    ],
                                ),
                            ],
                        ),
                        Field(
                            name="userErrors",
                            fields=[Field(name="field"), Field(name="message")],
                        ),
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
