from __future__ import annotations

import asyncio

import trafilatura

from railtracks.llm._url_fetch import fetch as guarded_fetch
from railtracks.llm.encoding import validate_max_mb

from ..models import FetchResult

_DEFAULT_USER_AGENT = "railtracks-websearch/1.0"


class HttpFetch:
    """FetchBackend using a plain HTTP GET + trafilatura extraction.

    Handles static/server-rendered pages. JS-heavy pages that render content
    client-side will typically come back with no extractable content; a
    headless-browser backend can be swapped in later for those via the same
    FetchBackend signature.

    The URL usually comes from the model, so the request goes through the same
    guarded fetch as attachment URLs: only `http`/`https`, only public
    addresses (checked again on every redirect), proxy settings ignored, and
    the body capped at `max_mb`.
    """

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        user_agent: str = _DEFAULT_USER_AGENT,
        max_mb: float = 10.0,
    ) -> None:
        """Create a guarded HTTP + trafilatura fetch backend.

        Args:
            timeout: Timeout in seconds for each connection and each read,
                not for the whole fetch.
            user_agent: Sent as the request's User-Agent header. Defaults to
                an honest, identifiable string rather than spoofing a real
                browser; some sites block bare HTTP-library user agents, and
                a few require a real browser UA to serve content at all —
                override this if you hit that.
            max_mb: Largest page accepted, in megabytes. Must be positive and
                finite. A larger page is reported as a failed fetch.

        Raises:
            ValueError: If `max_mb` is not positive and finite.
        """
        validate_max_mb(max_mb)
        self._timeout = timeout
        self._user_agent = user_agent
        self._max_mb = max_mb

    async def fetch(self, url: str) -> FetchResult:
        try:
            response = await asyncio.to_thread(
                guarded_fetch,
                url,
                timeout=self._timeout,
                max_mb=self._max_mb,
                user_agent=self._user_agent,
            )
        except (OSError, ValueError) as e:
            return FetchResult(
                url=url, is_error=True, error_message=f"Fetch failed: {e!r}"
            )

        html = response.text
        text = trafilatura.extract(html) or ""
        if not text:
            return FetchResult(
                url=url,
                is_error=True,
                error_message=(
                    "Page fetched but no extractable content (possibly "
                    "JS-rendered, blocked, or paywalled)."
                ),
            )

        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata is not None else None
        return FetchResult(url=url, title=title, text=text)
