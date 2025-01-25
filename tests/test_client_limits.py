from http import HTTPStatus

import pytest

from shopify_client import AsyncClient

from .utils import async_local_server_session, generate_opts_and_sess, local_server_session


@pytest.mark.usefixtures("local_server")
@local_server_session
async def test_graphql_retry():
    async with AsyncClient(*generate_opts_and_sess()) as c:
        response = await c.graphql(
            query="{ shop { name } }",
            headers={"x-test-status": f"{HTTPStatus.BAD_GATEWAY.value} {HTTPStatus.BAD_GATEWAY.phrase}"},
        )
        assert 502 in response.status
        assert response.retries == c.options.max_retries


@pytest.mark.usefixtures("local_server")
@local_server_session
async def test_graphql_cost_limit():
    async with AsyncClient(*generate_opts_and_sess()) as c:
        for i in range(2):
            c.options.time_store.append(c.session, c.options.deferrer.current_time())
        c.options.cost_store.append(c.session, 100)

        await c.graphql("{ shop { name } }")
        assert len(c.options.time_store.all(c.session)) == 1
        assert len(c.options.cost_store.all(c.session)) == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("local_server")
@async_local_server_session
async def test_async_graphql_cost_limit():
    async with AsyncClient(*generate_opts_and_sess()) as c:
        for i in range(2):
            c.options.time_store.append(c.session, c.options.deferrer.current_time())
        c.options.cost_store.append(c.session, 100)

        await c.graphql("{ shop { name } }")
        assert len(c.options.time_store.all(c.session)) == 1
        assert len(c.options.cost_store.all(c.session)) == 1
