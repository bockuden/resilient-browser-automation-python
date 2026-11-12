"""Live Chromium smoke test for owned browser and job resources."""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import Browser, BrowserContext, Page

from resilient_browser_automation import BrowserManager
from resilient_browser_automation.test_runs import TestRun as RunContext

pytestmark = pytest.mark.integration


def test_chromium_opens_page_and_closes_owned_resources(test_run: RunContext) -> None:
    async def run() -> None:
        manager = BrowserManager()
        browser: Browser | None = None
        context: BrowserContext | None = None
        page: Page | None = None

        async with manager:
            browser = manager.browser
            async with manager.open_job() as job:
                context = job.context
                page = job.page
                response = await page.goto(test_run.scenario_url("success"))
                assert response is not None
                assert response.status == 200
                assert await page.title() == "Deterministic demo catalog"

            assert page is not None and page.is_closed()
            assert context is not None and context.pages == []

        assert browser is not None
        assert not browser.is_connected()

    asyncio.run(run())
