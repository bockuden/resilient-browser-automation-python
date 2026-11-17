"""Live Chromium smoke test for owned browser and job resources."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from playwright.async_api import Browser, BrowserContext, Page

from resilient_browser_automation import BrowserManager, CatalogAdapter, CatalogEndReason
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


def test_job_contexts_do_not_share_authentication_state(test_run: RunContext) -> None:
    async def run() -> None:
        async with BrowserManager() as manager:
            async with manager.open_job() as first_job:
                await first_job.page.goto(f"{test_run.base_url}/health")
                await first_job.context.add_cookies(
                    [{"name": "session", "value": "first-job", "url": test_run.base_url}]
                )

                async with manager.open_job() as second_job:
                    first_cookies = await first_job.context.cookies()
                    second_cookies = await second_job.context.cookies()

                    assert any(cookie["value"] == "first-job" for cookie in first_cookies)
                    assert second_cookies == []

    asyncio.run(run())


def test_catalog_adapter_extracts_records_through_browser_pagination(test_run: RunContext) -> None:
    async def run() -> None:
        async with BrowserManager() as manager:
            async with manager.open_job() as job:
                response = await job.page.goto(test_run.scenario_url("success", total_pages=3))
                assert response is not None and response.status == 200

                result = await CatalogAdapter(job.page).extract(page_limit=3)

        assert result.end_reason is CatalogEndReason.NATURAL_END
        assert result.pages_collected == 3
        assert [record.item_id for record in result.records] == [
            f"item-{item_id:03d}" for item_id in range(1, 16)
        ]
        assert [record.price for record in result.records] == [
            Decimal(f"{item_id}.99") for item_id in range(1, 16)
        ]
        assert all(
            record.source_url == test_run.scenario_url("success", total_pages=3)
            for record in result.records
        )

    asyncio.run(run())
