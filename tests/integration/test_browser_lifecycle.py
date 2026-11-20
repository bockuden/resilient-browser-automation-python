"""Live Chromium smoke test for owned browser and job resources."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from playwright.async_api import Browser, BrowserContext, Page

from resilient_browser_automation import (
    BrowserManager,
    CatalogAdapter,
    CatalogEndReason,
    ExtractionContractError,
    TransientTargetError,
)
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

                committed_pages: list[tuple[int, int]] = []

                async def record_page(page_number: int, records: tuple[object, ...]) -> None:
                    committed_pages.append((page_number, len(records)))

                result = await CatalogAdapter(job.page).extract(page_limit=3, on_page=record_page)

        assert result.end_reason is CatalogEndReason.NATURAL_END
        assert result.pages_collected == 3
        assert committed_pages == [(1, 5), (2, 5), (3, 5)]
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


def test_catalog_adapter_reports_page_limit_separately(test_run: RunContext) -> None:
    async def run() -> None:
        async with BrowserManager() as manager:
            async with manager.open_job() as job:
                response = await job.page.goto(test_run.scenario_url("success", total_pages=4))
                assert response is not None and response.status == 200

                result = await CatalogAdapter(job.page).extract(page_limit=2)

        assert result.end_reason is CatalogEndReason.PAGE_LIMIT
        assert result.pages_collected == 2
        assert len(result.records) == 10

    asyncio.run(run())


def test_catalog_loading_failure_is_not_successful_empty_output(test_run: RunContext) -> None:
    async def run() -> None:
        async with BrowserManager() as manager:
            async with manager.open_job() as job:
                response = await job.page.goto(test_run.scenario_url("permanent"))
                assert response is not None and response.status == 200

                with pytest.raises(TransientTargetError, match="HTTP 500"):
                    await CatalogAdapter(job.page).extract(page_limit=1)

    asyncio.run(run())


def test_catalog_missing_item_marker_is_an_extraction_error(test_run: RunContext) -> None:
    async def run() -> None:
        async with BrowserManager() as manager:
            async with manager.open_job() as job:
                response = await job.page.goto(
                    test_run.scenario_url(
                        "selector-failure",
                        selector_failure_target="item",
                        selector_failure_mode="missing",
                        selector_failure_page=1,
                    )
                )
                assert response is not None and response.status == 200

                with pytest.raises(ExtractionContractError, match="item marker"):
                    await CatalogAdapter(job.page).extract(page_limit=1)

    asyncio.run(run())


def test_catalog_missing_next_page_marker_is_not_natural_end(test_run: RunContext) -> None:
    async def run() -> None:
        async with BrowserManager() as manager:
            async with manager.open_job() as job:
                response = await job.page.goto(
                    test_run.scenario_url(
                        "selector-failure",
                        total_pages=3,
                        selector_failure_target="next_page",
                        selector_failure_mode="missing",
                        selector_failure_page=1,
                    )
                )
                assert response is not None and response.status == 200

                with pytest.raises(ExtractionContractError, match="next-page control"):
                    await CatalogAdapter(job.page).extract(page_limit=3)

    asyncio.run(run())
