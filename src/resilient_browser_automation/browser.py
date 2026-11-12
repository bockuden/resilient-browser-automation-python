"""Asynchronous ownership boundary for a shared browser and per-job contexts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import TracebackType

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class BrowserJob:
    """One job's isolated browser context and its initial page."""

    def __init__(self, browser: Browser) -> None:
        self._browser = browser
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def context(self) -> BrowserContext:
        """Return this job's owned context while it is active."""

        if self._context is None:
            raise RuntimeError("browser job is not active")
        return self._context

    @property
    def page(self) -> Page:
        """Return this job's initial page while it is active."""

        if self._page is None:
            raise RuntimeError("browser job is not active")
        return self._page

    async def __aenter__(self) -> BrowserJob:
        if self._context is not None:
            raise RuntimeError("browser job context is already active")
        context = await self._browser.new_context()
        try:
            page = await context.new_page()
        except BaseException as initialization_error:
            await _cleanup_preserving_error(context.close, initialization_error)
            raise
        self._context = context
        self._page = page
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, exc, traceback
        context = self._context
        self._context = None
        self._page = None
        if context is not None:
            await context.close()
        return False


class BrowserManager:
    """Own one Playwright driver/browser; create an isolated context per job."""

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    @property
    def browser(self) -> Browser:
        """Expose the shared browser process for diagnostics and lifecycle checks."""

        if self._browser is None:
            raise RuntimeError("browser manager is not active")
        return self._browser

    def open_job(self) -> BrowserJob:
        """Create a job scope; each call creates a new, isolated context."""

        return BrowserJob(self.browser)

    async def __aenter__(self) -> BrowserManager:
        if self._playwright is not None or self._browser is not None:
            raise RuntimeError("browser manager is already active")
        playwright = await async_playwright().start()
        try:
            browser = await playwright.chromium.launch(headless=self._headless)
        except BaseException as initialization_error:
            await _cleanup_preserving_error(playwright.stop, initialization_error)
            raise
        self._playwright = playwright
        self._browser = browser
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, exc, traceback
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        try:
            if browser is not None:
                await browser.close()
        finally:
            if playwright is not None:
                await playwright.stop()
        return False


async def _cleanup_preserving_error(
    cleanup: Callable[[], Awaitable[object]], original_error: BaseException
) -> None:
    try:
        await cleanup()
    except BaseException as cleanup_error:
        original_error.add_note(f"Resource cleanup also failed ({type(cleanup_error).__name__}).")
