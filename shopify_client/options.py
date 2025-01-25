import re
from http import HTTPStatus

from .constants import ALT_MODE, DEFAULT_MODE, DEFAULT_VERSION, VERSION_PATTERN
from .deferrer import SleepDeferrer
from .store import CostMemoryStore, TimeMemoryStore


class Options(object):
    def __init__(self):
        # Number of retries that should happen if failed
        self.max_retries = 2
        # Retry if status is 422, 5xx
        self.retry_on_status = [
            HTTPStatus.TOO_MANY_REQUESTS.value,
            HTTPStatus.BAD_GATEWAY.value,
            HTTPStatus.SERVICE_UNAVAILABLE.value,
            HTTPStatus.GATEWAY_TIMEOUT.value,
        ]
        # Always send these headers with every request
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        # Time storage implementation
        self.time_store = TimeMemoryStore()
        # Cost storage implementation
        self.cost_store = CostMemoryStore()
        # Deferrer implementation for getting current time and sleeping
        self.deferrer = SleepDeferrer()
        # Number of cost points allowed per second for GraphQL... 50 for regular, 100 for plus
        self.graphql_limit = 50
        # Methods to run before firing GraphQL API calls
        self.graphql_pre_actions = []
        # Methods to run after firing GraphQL API calls
        self.graphql_post_actions = []
        # Version to use for API calls
        self._version = DEFAULT_VERSION
        # Mode to use... public or private
        self._mode = DEFAULT_MODE

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, value: str) -> None:
        if not bool(re.match(VERSION_PATTERN, value)):
            raise ValueError(f"Version: {value} does not match YYYY-MM format or unstable")
        self._version = value

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value != DEFAULT_MODE and value != ALT_MODE:
            raise ValueError(f"Type must be either {DEFAULT_MODE} or {ALT_MODE}")
        self._mode = value

    @property
    def is_public(self) -> bool:
        return self.mode == DEFAULT_MODE

    @property
    def is_private(self) -> bool:
        return not self.is_public
