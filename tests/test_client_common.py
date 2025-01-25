from shopify_client.client import AsyncClient
from shopify_client.constants import ACCESS_TOKEN_HEADER, ALT_MODE

from .utils import generate_opts_and_sess


async def test_build_headers():
    async with AsyncClient(*generate_opts_and_sess()) as c:
        headers = c._build_headers({})
        assert headers[ACCESS_TOKEN_HEADER] == "123"

    async with AsyncClient(*generate_opts_and_sess(ALT_MODE)) as c:
        headers = c._build_headers({})
        assert ACCESS_TOKEN_HEADER not in headers


async def test_build_request():
    async with AsyncClient(*generate_opts_and_sess()) as c:
        request = c._build_request(
            method="get",
            path="/admin/api/shop.json",
            params={"fields": "id"},
        )
        assert "params" in request
        assert "2020-04" in request["url"]

        request = c._build_request(
            method="post",
            path="/admin/api/shop.json",
            params={"fields": "id"},
        )
        assert "json" in request
