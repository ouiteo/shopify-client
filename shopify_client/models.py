from http import HTTPStatus
from typing import Optional

from httpx._models import Response

from .types import ParsedBody, ParsedError


class Session:
    def __init__(
        self,
        domain: Optional[str] = None,
        key: Optional[str] = None,
        password: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.domain = domain
        self.key = key
        self.password = password
        self.secret = secret

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}"


class ApiResult:
    def __init__(
        self,
        response: Response,
        status: HTTPStatus,
        body: ParsedBody,
        errors: ParsedError,
        retries: int = 0,
    ):
        self.response = response
        self.status = (status,)
        self.body = body
        self.errors = errors
        self.retries = retries
