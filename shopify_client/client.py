import asyncio
import logging
from http import HTTPStatus
from pathlib import Path
from types import TracebackType
from typing import Any, Optional, Self, Type, cast
from urllib.parse import urlencode

import httpx
from httpx._types import RequestContent
from tenacity import retry, retry_if_exception_type, wait_exponential

from .builder import ShopifyQuery
from .exceptions import BulkQueryInProgress, QueryError, RetriableException, ThrottledException
from .types import ShopifyWebhookTopic, WebhookSubscriptionInput
from .utils import get_error_codes

logger = logging.getLogger(__name__)
GQL_DIR = Path(__file__).parent / "gql"

retry_on_status = [
    HTTPStatus.TOO_MANY_REQUESTS.value,
    HTTPStatus.BAD_GATEWAY.value,
    HTTPStatus.SERVICE_UNAVAILABLE.value,
    HTTPStatus.GATEWAY_TIMEOUT.value,
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
    def parse_query(query: str) -> str:
        return " ".join([x.strip() for x in query.split("\n")])

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
    async def graphql(self, query: ShopifyQuery, variables: dict[str, Any] = {}) -> dict[str, Any]:
        """
        Execute a GraphQL query against the Shopify API.

        Args:
            query: A ShopifyQuery instance that defines the query structure
            variables: Variables to pass to the query

        Returns:
            The parsed JSON response from the API

        Raises:
            QueryError: If the query contains errors
            RetriableException: If the request should be retried due to temporary issues

        Example:
            >>> builder = ShopifyQuery("shop", ["name"])
            >>> response = await client.graphql(builder)
        """
        json_data = {"query": str(query), "variables": variables}
        response = await self.session.post(self.base_url, json=json_data)
        if response.status_code in retry_on_status:
            raise RetriableException(f"retrying http {response.status_code}")

        response.raise_for_status()
        data = cast(dict[str, Any], response.json())

        error_codes = get_error_codes(data)
        if error_codes:
            if "THROTTLED" in error_codes:
                raise ThrottledException(data.get("errors") or data.get("error"))
            raise QueryError(data.get("errors") or data.get("error"))

        return data

    async def graphql_call_with_pagination(
        self, query: ShopifyQuery, variables: dict[str, Any] = {}, max_limit: int | None = None
    ) -> list[dict[str, Any]] | None:
        """
        Make a graphql query with pagination using a ShopifyQuery instance.

        Args:
            query: The ShopifyQuery instance that defines the query structure
            variables: The variables to pass to the query
            max_limit: Maximum number of items to return

        Returns:
            A list of entity data, or None if no data is found

        Example:
            >>> builder = ShopifyQuery("products", ["id", "title", "handle"], args={"first": 250})
            >>> data = await client.graphql_call_with_pagination(builder)
        """
        has_next_page = True
        end_cursor: str | None = None
        data = []

        # Ensure the query includes pagination fields
        if not any(field == "pageInfo" for field in query.fields):
            query.fields.append("pageInfo")
        if not any(field == "edges" for field in query.fields):
            query.fields.append("edges")

        while has_next_page:
            variables["cursor"] = end_cursor
            response = await self.graphql(query, variables)

            # Navigate to the entity data
            entity_data = response.get("data", {}).get(query.entity, {})
            if not entity_data:
                return None

            page_info = entity_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor", None)
            entity_data.pop("pageInfo", None)

            # Extract node data from edges
            for edge in entity_data.get("edges", []):
                data.append(edge.get("node", {}))

            if max_limit and len(data) >= max_limit:
                return data[:max_limit]

        return data

    async def is_bulk_job_running(self, job_type: str) -> bool:
        """
        Check if a bulk operation is running
        job_type: "QUERY" or "MUTATION"
        """
        query = ShopifyQuery(
            operation_name="currentBulkOperation",
            entity="currentBulkOperation",
            fields=[
                "id",
                "status",
                "errorCode",
                "createdAt",
                "completedAt",
                "objectCount",
                "fileSize",
                "url",
                "partialDataUrl",
            ],
            args={"type": job_type},
        )
        response = await self.graphql(query)
        current_bulk_operation = response["data"]["currentBulkOperation"]
        if current_bulk_operation is not None and current_bulk_operation["status"] in ["CREATED", "RUNNING"]:
            return True

        return False

    async def poll_until_complete(self, job_id: str, job_type: str) -> str | None:
        """
        Poll the bulk operation until it is complete, then return the dataframe
        """
        query = ShopifyQuery(
            operation_name="currentBulkOperation",
            entity="currentBulkOperation",
            fields=[
                "id",
                "status",
                "errorCode",
                "createdAt",
                "completedAt",
                "objectCount",
                "fileSize",
                "url",
                "partialDataUrl",
            ],
            args={"type": job_type},
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
        self, sub_query: ShopifyQuery, variables: dict[str, Any] = {}, wait: bool = True
    ) -> str | None:
        # check if any bulk query job in progress currently
        is_job_running = await self.is_bulk_job_running(job_type="QUERY")
        if is_job_running:
            raise BulkQueryInProgress("Bulk query job already running")

        query = ShopifyQuery(
            operation_name="bulkOperationRunQuery",
            entity="bulkOperationRunQuery",
            fields=[
                {"name": "bulkOperation", "fields": ["id", "status"]},
                {"name": "userErrors", "fields": ["field", "message"]},
            ],
            args={"query": str(sub_query)},
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
        self, sub_query: ShopifyQuery, variables: dict[str, Any] = {}, wait: bool = True
    ) -> str | None:
        # check if any bulk mutation job in progress currently
        is_job_running = await self.is_bulk_job_running(job_type="MUTATION")
        if is_job_running:
            raise ValueError("Bulk mutation job already running")

        query = ShopifyQuery(
            operation_name="bulkOperationRunMutation",
            entity="bulkOperationRunMutation",
            fields=[
                {"name": "bulkOperation", "fields": ["id", "status"]},
                {"name": "userErrors", "fields": ["field", "message"]},
            ],
            args={"mutation": str(sub_query)},
            query_type="mutation",
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
        """
        Get all webhook subscriptions
        """
        query = ShopifyQuery(
            operation_name="webhookSubscriptions",
            entity="webhookSubscriptions",
            fields=[
                "id",
                "topic",
                {
                    "name": "endpoint",
                    "fields": [
                        {"name": "__typename ... on WebhookHttpEndpoint", "fields": ["callbackUrl"]},
                        {"name": "... on WebhookEventBridgeEndpoint", "fields": ["arn"]},
                    ],
                },
            ],
            args={"first": 250},
        )
        response = await self.graphql(query)
        return [edge["node"] for edge in response["data"]["webhookSubscriptions"]["edges"]]

    async def subscribe_to_topic(self, topic: ShopifyWebhookTopic, subscription: WebhookSubscriptionInput) -> None:
        """
        Subscribe to a webhook topic
        """
        query = ShopifyQuery(
            operation_name="webhookSubscriptionCreate",
            entity="webhookSubscription",
            fields=[
                "id",
                "topic",
                {
                    "name": "endpoint",
                    "fields": [
                        {"name": "__typename ... on WebhookHttpEndpoint", "fields": ["callbackUrl"]},
                        {"name": "... on WebhookEventBridgeEndpoint", "fields": ["arn"]},
                    ],
                },
                {
                    "name": "webhookSubscription",
                    "fields": ["id", "topic", "filter", "format", "endpoint"],
                },
                {"name": "userErrors", "fields": ["field", "message"]},
            ],
            args={"topic": "WebhookSubscriptionTopic!", "webhookSubscription": "WebhookSubscriptionInput!"},
            query_type="mutation",
        )
        response = await self.graphql(query, variables={"topic": topic.value, "webhookSubscription": subscription})
        user_errors = response["data"]["webhookSubscriptionCreate"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)
