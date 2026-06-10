import httpx

from app.core.config import settings
from app.core.resilience import with_retries


class FirecrawlClient:
    base_url = "https://api.firecrawl.dev/v2"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def search(self, query: str, limit: int = 5, lang: str = "zh", country: str = "CN") -> dict:
        """Firecrawl v2 search 端点（与 v1/scrape 平级，可作为 Tavily 失败后的轮询 fallback）。"""
        def operation() -> dict:
            response = httpx.post(
                f"{self.base_url}/search",
                headers=self._headers,
                json={
                    "query": query,
                    "limit": max(1, min(20, int(limit))),
                    "lang": lang,
                    "country": country,
                },
                timeout=settings.external_request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()

        return with_retries(
            operation,
            retries=settings.external_request_retries,
            retry_exceptions=(httpx.HTTPError,),
        )

    def scrape(self, url: str) -> dict:
        def operation() -> dict:
            response = httpx.post(
                f"{self.base_url}/scrape",
                headers=self._headers,
                json={"url": url},
                timeout=settings.external_request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()

        return with_retries(
            operation,
            retries=settings.external_request_retries,
            retry_exceptions=(httpx.HTTPError,),
        )


def build_firecrawl_client() -> FirecrawlClient | None:
    if not settings.firecrawl_key:
        return None
    return FirecrawlClient(settings.firecrawl_key)
