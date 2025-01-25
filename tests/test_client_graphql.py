from unittest.mock import AsyncMock

import jsonlines
import pytest
from httpx import Response as HttpxResponse
from pytest_httpx._httpx_mock import HTTPXMock

from shopify_client import AsyncClient

from .utils import async_local_server_session, generate_opts_and_sess, local_server_session


@pytest.mark.usefixtures("local_server")
@local_server_session
async def test_graphql_return(local_server):
    async with AsyncClient(*generate_opts_and_sess()) as c:
        response = await c.graphql("{ shop { name } }")
        assert isinstance(response.body, dict)
        assert response.body["data"]["shop"]["name"] == "Apple Computers"
        assert response.errors is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_graphql_async_return(local_server):
    async with AsyncClient(*generate_opts_and_sess()) as c:
        response = await c.graphql("{ shop { name } }")
        assert isinstance(response.body, dict)
        assert response.body["data"]["shop"]["name"] == "Apple Computers"
        assert response.errors is None


@pytest.mark.asyncio
@pytest.mark.parametrize("max_limit", [(1), (2)])
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_graphql_pagination_data(local_server, mock_graphql_response: AsyncMock, max_limit: int) -> None:
    async with AsyncClient(*generate_opts_and_sess()) as c:
        mock_graphql_response("product.json")
        response = await c.graphql_call_with_pagination("products", "Query", {}, max_limit)
        assert len(response) == max_limit


@pytest.mark.asyncio
@pytest.mark.parametrize("job_status, expected", [("RUNNING", True), ("COMPLETED", False)])
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_is_bulk_job_running(
    local_server, mock_graphql_response: AsyncMock, job_status: str, expected: bool
) -> None:
    async with AsyncClient(*generate_opts_and_sess()) as c:
        mock_graphql_response(f"bulk_job_{job_status.lower()}.json")
        response = await c.is_bulk_job_running("QUERY")
        assert response == expected


@pytest.mark.asyncio
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_poll_until_complete(local_server, mock_graphql_response: AsyncMock, httpx_mock: HTTPXMock) -> None:
    async with AsyncClient(*generate_opts_and_sess()) as c:
        job_id = "gid://shopify/BulkOperation/1"
        url = "https://download.com"
        mocked_response = "Data Downloaded"
        mock_graphql_response("bulk_job_completed.json")
        httpx_mock.add_response(url=url, text=mocked_response)
        response = await c.poll_until_complete(job_id, "QUERY")
        assert response.text == mocked_response


@pytest.mark.asyncio
@pytest.mark.parametrize("expected_type, wait", [(str, False), (jsonlines.Reader, True)])
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_run_bulk_operation_query(
    local_server, mock_graphql_response: AsyncMock, monkeypatch: pytest.MonkeyPatch, expected_type: type, wait: bool
) -> None:
    async with AsyncClient(*generate_opts_and_sess()) as c:
        mock_graphql_response("bulk_submit_query.json")

        job_running = AsyncMock(return_value=False)
        monkeypatch.setattr("shopify_client.clients.async_client.AsyncClient.is_bulk_job_running", job_running)

        complete_response = AsyncMock(
            return_value=HttpxResponse(status_code=204, content=b'{"data": {"entity": "data"}}')
        )
        monkeypatch.setattr("shopify_client.clients.async_client.AsyncClient.poll_until_complete", complete_response)

        response = await c.run_bulk_operation_query("query", {}, wait)
        assert isinstance(response, expected_type)


@pytest.mark.asyncio
@pytest.mark.parametrize("expected_type, wait", [(str, False), (jsonlines.Reader, True)])
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_run_bulk_operation_mutation(
    local_server,
    mock_graphql_response: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
    expected_type: type,
    wait: bool,
) -> None:
    async with AsyncClient(*generate_opts_and_sess()) as c:
        mock_graphql_response("create_and_submit_mutation.json")
        httpx_mock.add_response(url="https://upload.com", text="Data Uploaded")

        complete_response = AsyncMock(
            return_value=HttpxResponse(status_code=204, content=b'{"data": {"entity": "data"}}')
        )
        monkeypatch.setattr("shopify_client.clients.async_client.AsyncClient.poll_until_complete", complete_response)

        row_data = [{"field1": "value1", "field2": "value2"}]
        response = await c.run_bulk_operation_mutation("query", row_data, "input", wait)
        assert isinstance(response, expected_type)
