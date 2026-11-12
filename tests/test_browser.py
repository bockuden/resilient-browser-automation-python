"""Unit tests for partial and failed browser resource initialization."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from playwright.async_api import Browser, BrowserContext, Page, Playwright

import resilient_browser_automation.browser as browser_module
from resilient_browser_automation.browser import BrowserJob, BrowserManager


class InitializationFailure(RuntimeError):
    """Failure injected at a browser resource boundary."""


class FakePage:
    pass


class FakeContext:
    def __init__(self, *, page_error: BaseException | None = None) -> None:
        self.page_error = page_error
        self.closed = False

    async def new_page(self) -> Page:
        if self.page_error is not None:
            raise self.page_error
        return cast(Page, FakePage())

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext) -> None:
        self.context = context

    async def new_context(self) -> BrowserContext:
        return cast(BrowserContext, self.context)


class FakeChromium:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def launch(self, *, headless: bool) -> Browser:
        del headless
        raise self.error


class FakePlaywright:
    def __init__(self, launch_error: BaseException) -> None:
        self.chromium = FakeChromium(launch_error)
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakePlaywrightStarter:
    def __init__(self, playwright: FakePlaywright) -> None:
        self.playwright = playwright

    async def start(self) -> Playwright:
        return cast(Playwright, self.playwright)


def test_launch_failure_stops_partially_initialized_playwright(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = InitializationFailure("chromium launch failed")
    playwright = FakePlaywright(failure)
    monkeypatch.setattr(
        browser_module,
        "async_playwright",
        lambda: FakePlaywrightStarter(playwright),
    )

    async def run() -> None:
        manager = BrowserManager()
        with pytest.raises(InitializationFailure, match="chromium launch failed"):
            await manager.__aenter__()
        assert playwright.stopped
        with pytest.raises(RuntimeError, match="not active"):
            _ = manager.browser

    asyncio.run(run())


def test_page_initialization_failure_closes_owned_context() -> None:
    failure = InitializationFailure("page creation failed")
    context = FakeContext(page_error=failure)
    job = BrowserJob(cast(Browser, FakeBrowser(context)))

    async def run() -> None:
        with pytest.raises(InitializationFailure, match="page creation failed"):
            await job.__aenter__()
        assert context.closed
        with pytest.raises(RuntimeError, match="not active"):
            _ = job.context

    asyncio.run(run())


def test_operation_failure_closes_the_owned_context() -> None:
    context = FakeContext()
    job = BrowserJob(cast(Browser, FakeBrowser(context)))
    failure = InitializationFailure("job operation failed")

    async def run() -> None:
        with pytest.raises(InitializationFailure, match="job operation failed"):
            async with job:
                raise failure
        assert context.closed

    asyncio.run(run())
