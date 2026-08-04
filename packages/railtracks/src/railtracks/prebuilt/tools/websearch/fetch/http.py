from __future__ import annotations

import httpx
import trafilatura

from ..models import FetchResult

_DEFAULT_USER_AGENT = "railtracks-websearch/1.0"


class HttpFetch:
    """FetchBackend using a plain HTTP GET + trafilatura extraction.

    Handles static/server-rendered pages. JS-heavy pages that render content
    client-side will typically come back with no extractable content; a
    headless-browser backend can be swapped in later for those via the same
    FetchBackend signature.
    """

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        user_agent: str = _DEFAULT_USER_AGENT,
    ) -> None:
        """Create an httpx + trafilatura fetch backend.

        Args:
            timeout: Request timeout in seconds before the fetch is treated
                as failed.
            user_agent: Sent as the request's User-Agent header. Defaults to
                an honest, identifiable string rather than spoofing a real
                browser; some sites block bare HTTP-library user agents, and
                a few require a real browser UA to serve content at all —
                override this if you hit that.
        """
        self._timeout = timeout
        self._user_agent = user_agent

    async def fetch(self, url: str) -> FetchResult:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            return FetchResult(
                url=url, is_error=True, error_message=f"Fetch failed: {e}"
            )

        text = trafilatura.extract(resp.text) or ""
        if not text:
            return FetchResult(
                url=url,
                is_error=True,
                error_message=(
                    "Page fetched but no extractable content (possibly "
                    "JS-rendered, blocked, or paywalled)."
                ),
            )

        metadata = trafilatura.extract_metadata(resp.text)
        title = metadata.title if metadata is not None else None
        return FetchResult(url=url, title=title, text=text)
