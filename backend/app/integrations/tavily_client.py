from tavily import TavilyClient

from app.core.config import settings
from app.core.resilience import with_retries


class ResilientTavilyClient:
    def __init__(self, api_key: str) -> None:
        self._client = TavilyClient(api_key)

    def search(self, **kwargs) -> dict:
        return with_retries(
            lambda: self._client.search(**kwargs),
            retries=settings.external_request_retries,
        )


def build_tavily_client() -> ResilientTavilyClient | None:
    if not settings.tavily_key:
        return None
    return ResilientTavilyClient(settings.tavily_key)
