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
        del exc_type, traceback
        context = self._context
        self._context = None
        self._page = None
        if context is not None:
            try:
                await context.close()
            except BaseException as cleanup_error:
                if exc is None:
                    raise
                _add_cleanup_note(exc, cleanup_error, "job browser context")
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
        del exc_type, traceback
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        resources: tuple[tuple[str, Callable[[], Awaitable[object | None]]], ...] = tuple(
            (name, close)
            for name, close in (
                ("browser", browser.close if browser is not None else None),
                ("Playwright driver", playwright.stop if playwright is not None else None),
            )
            if close is not None
        )
        cleanup_errors: list[tuple[str, BaseException]] = []
        for name, close in resources:
            try:
                await close()
            except BaseException as cleanup_error:
                if exc is not None:
                    _add_cleanup_note(exc, cleanup_error, name)
                else:
                    cleanup_errors.append((name, cleanup_error))
        if exc is None and cleanup_errors:
            primary_error = cleanup_errors[0][1]
            for name, secondary_error in cleanup_errors[1:]:
                _add_cleanup_note(primary_error, secondary_error, name)
            raise primary_error
        return False


async def _cleanup_preserving_error(
    cleanup: Callable[[], Awaitable[object | None]], original_error: BaseException
) -> None:
    try:
        await cleanup()
    except BaseException as cleanup_error:
        _add_cleanup_note(original_error, cleanup_error, "partially initialized resource")


def _add_cleanup_note(
    original_error: BaseException, cleanup_error: BaseException, resource_name: str
) -> None:
    original_error.add_note(
        f"Cleanup of {resource_name} also failed ({type(cleanup_error).__name__})."
    )
