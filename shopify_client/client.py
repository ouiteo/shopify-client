import asyncio
import logging
import uuid
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, Optional, Self, Type, cast
from urllib.parse import urlencode

import httpx
import jsonlines
from httpx._types import RequestContent
from jsonlines import Reader
from tenacity import retry, retry_if_exception_type, wait_exponential

from .exceptions import QueryError, RetriableException
from .types import ShopifyWebhookSubscription, ShopifyWebhookTopic

logger = logging.getLogger(__name__)
GQL_DIR = Path(__file__).parent / "gql"

retry_on_status = [
    HTTPStatus.TOO_MANY_REQUESTS.value,
    HTTPStatus.BAD_GATEWAY.value,
    HTTPStatus.SERVICE_UNAVAILABLE.value,
    HTTPStatus.GATEWAY_TIMEOUT.value,
]

if TYPE_CHECKING:
    import pandas as pd


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
    async def pandas_response(data_url: Optional[str]) -> "pd.DataFrame":
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for pandas response type")

        if not data_url:
            return pd.DataFrame()

        return pd.read_json(data_url, lines=True)

    @staticmethod
    async def jsonlines_response(data_url: Optional[str]) -> "jsonlines.Reader":
        if not data_url:
            return Reader(BytesIO(b""))

        async with httpx.AsyncClient() as client:
            response = await client.get(data_url)
            response.raise_for_status()

        return Reader(BytesIO(response.content))

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
    async def graphql(self, query: str, variables: dict[str, Any] = {}) -> dict[str, Any]:
        json_data = {"query": query, "variables": variables}
        response = await self.session.post(self.base_url, json=json_data)
        if response.status_code in retry_on_status:
            raise RetriableException(f"retrying http {response.status_code}")

        response.raise_for_status()
        data = cast(dict[str, Any], response.json())

        if data.get("errors") or data.get("error"):
            raise QueryError(data.get("errors") or data.get("error"))

        return data

    async def graphql_call_with_pagination(
        self, entity: str, query: str, variables: dict[str, Any] = {}, max_limit: int | None = None
    ) -> list[dict[str, Any]] | None:
        """
        Make a graphql query with pagination

        :param entity: The entity to fetch, e.g "products", "orders"
        :param query: The query to run
        :param variables: The variables to pass to the query

        :return: A list of entity data
        """
        has_next_page = True
        end_cursor: str | None = None
        data = []

        query = self.parse_query(query)

        while has_next_page:
            variables["cursor"] = end_cursor

            response = await self.graphql(query, variables)
            entity_path = entity.split(".")
            entity_data = response.get("data", {})

            for key in entity_path:
                entity_data = entity_data.get(key, {})
                if not entity_data:
                    return None

            page_info = entity_data.get("pageInfo", {})

            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor", None)
            entity_data.pop("pageInfo", None)

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
        query = open(GQL_DIR / "current_bulkoperation.gql").read() % {"job_type": job_type}
        query = self.parse_query(query)
        response = await self.graphql(query)
        current_bulk_operation = response["data"]["currentBulkOperation"]
        if current_bulk_operation is not None and current_bulk_operation["status"] in ["CREATED", "RUNNING"]:
            return True

        return False

    async def poll_until_complete(
        self, job_id: str, job_type: str, response_type: Literal["jsonlines", "pandas"] = "jsonlines"
    ) -> "Reader | pd.DataFrame":
        """
        Poll the bulk operation until it is complete, then return the dataframe
        """
        query = open(GQL_DIR / "current_bulkoperation.gql").read() % {"job_type": job_type}
        query = self.parse_query(query)
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
            if response_type == "jsonlines":
                return await self.jsonlines_response(data_url)

            elif response_type == "pandas":
                return await self.pandas_response(data_url)

        raise ValueError(f"Job failed with status {status} [{bulk_check_response}]")

    async def run_bulk_operation_query(
        self,
        sub_query: str,
        variables: dict[str, Any] = {},
        wait: bool = True,
        return_type: Literal["jsonlines", "pandas"] = "jsonlines",
    ) -> "str | jsonlines.Reader | pd.DataFrame":
        # check if any bulk query job in progress currently
        is_job_running = await self.is_bulk_job_running(job_type="QUERY")
        if is_job_running:
            raise ValueError("Bulk query job already running")

        query = open(GQL_DIR / "query_bulkoperation.gql").read() % {"sub_query": sub_query}

        query = self.parse_query(query)
        response = await self.graphql(query, variables)

        user_errors = response["data"]["bulkOperationRunQuery"]["userErrors"]
        if user_errors:
            raise QueryError(user_errors)

        job_id: str = response["data"]["bulkOperationRunQuery"]["bulkOperation"]["id"]
        if wait:
            return await self.poll_until_complete(job_id, "QUERY", response_type=return_type)

        return job_id

    async def run_bulk_operation_mutation(
        self,
        query: str,
        rows: list[dict[str, Any]],
        key: str | None = "input",
        wait: bool = True,
        return_type: Literal["jsonlines", "pandas"] = "jsonlines",
    ) -> "str | jsonlines.Reader | pd.DataFrame":
        """
        Run a GQL mutation in bulk

        Supported operations: https://shopify.dev/docs/api/usage/bulk-operations/imports#limitations
        rows are expected to have ONLY the fields that you wish to change.
        """
        filename = f"{uuid.uuid4()}.jsonl"
        stage_mutation_query = open(GQL_DIR / "mutation_upload_bulkoperation.gql").read() % {"filename": filename}

        ###################
        # Stage Mutations #
        ###################
        # Get the upload parameters for our mutation file
        stage_mutation_query = self.parse_query(stage_mutation_query)
        stage_mutations_response = await self.graphql(stage_mutation_query)

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
        bulk_mutation_query = open(GQL_DIR / "mutation_bulkoperation.gql").read() % {
            "mutation_query": query,
            "staged_upload_path": staged_upload_path,
        }

        # Perform the bulk mutation, and wait for its response
        bulk_mutation_query = self.parse_query(bulk_mutation_query)
        response = await self.graphql(bulk_mutation_query)

        user_errors = response["data"]["bulkOperationRunMutation"]["userErrors"]
        if user_errors:
            raise ValueError(user_errors)

        job_id: str = response["data"]["bulkOperationRunMutation"]["bulkOperation"]["id"]
        if not wait:
            return job_id

        return await self.poll_until_complete(job_id, "MUTATION", response_type=return_type)

    async def get_webhook_subscriptions(self) -> list[dict[str, Any]]:
        """
        Get all webhook subscriptions
        """
        query = open(GQL_DIR / "webhooks_list.gql").read()
        query = self.parse_query(query)
        response = await self.graphql(query)
        data: list[dict[str, Any]] = response["data"]["webhookSubscriptions"]["edges"]

        return data

    async def subscribe_to_topic(self, topic: ShopifyWebhookTopic, subscription: ShopifyWebhookSubscription) -> None:
        """
        Subscribe customer to the given webhook topic
        """
        query = open(GQL_DIR / "webhooks_subscribe.gql").read()
        query = self.parse_query(query)
        response = await self.graphql(query, {"topic": topic.name, "webhookSubscription": subscription})

        user_errors = response["data"]["eventBridgeWebhookSubscriptionCreate"]["userErrors"]
        if user_errors:
            raise ValueError(user_errors)
