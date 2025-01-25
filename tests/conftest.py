import json
import os
from http import HTTPStatus
from multiprocessing import Process
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock
from wsgiref.simple_server import make_server

import pytest
from httpx._models import Response

from shopify_client.constants import RETRY_HEADER
from shopify_client.models import ApiResult
from shopify_client.types import ParsedError


def local_server_app(environ, start_response):
    method = environ["REQUEST_METHOD"].lower()
    path = environ["PATH_INFO"].split("/")[-1]
    status = environ.get("HTTP_X_TEST_STATUS", f"{HTTPStatus.OK.value} {HTTPStatus.OK.description}")
    headers = [("Content-Type", "application/json")]
    fixture = environ.get("HTTP_X_TEST_FIXTURE", f"{method}_{path}")
    if "HTTP_X_TEST_RETRY" in environ:
        headers.append((RETRY_HEADER, environ["HTTP_X_TEST_RETRY"]))

    with open(os.path.dirname(__file__) + f"/fixtures/{fixture}") as fixture:
        data = fixture.read().encode("utf-8")

    start_response(status, headers)
    return [data]


@pytest.fixture
def local_server():
    httpd = make_server("localhost", 8080, local_server_app)
    process = Process(target=httpd.serve_forever, daemon=True)
    process.start()
    yield
    process.terminate()
    process.join()


@pytest.fixture
def mock_graphql_response(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    def set_response(
        fixture: str,
        response: Response = Response(status_code=200),
        status: HTTPStatus = HTTPStatus.OK,
        errors: ParsedError = None,
    ) -> Any:
        data = json.load(open(Path(__file__).parent / "fixtures" / fixture))
        api_result = ApiResult(response=response, status=status, body=data, errors=errors)

        return_resopnse = AsyncMock(return_value=api_result)
        monkeypatch.setattr("shopify_client.clients.async_client.AsyncClient.graphql", return_resopnse)

    yield set_response
