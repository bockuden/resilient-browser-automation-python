"""Browser-based extraction of a paginated catalog."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from playwright.async_api import Page

from resilient_browser_automation.errors import ExtractionContractError


@dataclass(frozen=True, slots=True)
class CatalogRecord:
    """One item observed in the browser, with its source page URL."""

    item_id: str
    name: str
    price: Decimal
    source_url: str


class CatalogEndReason(StrEnum):
    """Why catalog extraction stopped."""

    NATURAL_END = "natural_end"
    PAGE_LIMIT = "page_limit"


@dataclass(frozen=True, slots=True)
class CatalogResult:
    """Records gathered before a natural end or configured page limit."""

    records: tuple[CatalogRecord, ...]
    pages_collected: int
    end_reason: CatalogEndReason


class CatalogAdapter:
    """Extract catalog items through observable browser interactions."""

    def __init__(self, page: Page, *, readiness_timeout_ms: int = 10_000) -> None:
        if readiness_timeout_ms <= 0:
            raise ValueError("readiness_timeout_ms must be positive")
        self._page = page
        self._readiness_timeout_ms = readiness_timeout_ms

    async def extract(self, *, page_limit: int) -> CatalogResult:
        """Read each loaded page and follow its next-page control."""

        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or page_limit <= 0:
            raise ValueError("page_limit must be a positive integer")

        records: list[CatalogRecord] = []
        page_number = 1
        while True:
            await self._wait_for_page(page_number)
            records.extend(await self._read_records())
            next_page = self._page.get_by_test_id("next-page")
            if await next_page.count() == 0:
                return CatalogResult(tuple(records), page_number, CatalogEndReason.NATURAL_END)
            if page_number == page_limit:
                return CatalogResult(tuple(records), page_number, CatalogEndReason.PAGE_LIMIT)

            await next_page.click()
            page_number += 1

    async def _wait_for_page(self, page_number: int) -> None:
        status = self._page.get_by_role("status")
        await status.wait_for(state="visible", timeout=self._readiness_timeout_ms)
        await self._page.wait_for_function(
            "([number]) => { const status = document.querySelector('[role=status]'); "
            "return status && (status.dataset.state === 'error' || "
            "(status.dataset.state === 'success' && "
            "status.textContent.includes(`Page ${number} loaded`))); }",
            arg=[page_number],
            timeout=self._readiness_timeout_ms,
        )

    async def _read_records(self) -> list[CatalogRecord]:
        catalog = self._page.get_by_test_id("catalog")
        items = catalog.get_by_test_id("catalog-item")
        records: list[CatalogRecord] = []
        for index in range(await items.count()):
            item = items.nth(index)
            item_id = await item.get_attribute("data-item-id")
            name = (await item.get_by_test_id("item-name").inner_text()).strip()
            raw_price = (await item.get_by_test_id("item-price").inner_text()).strip()
            if not item_id or not name:
                raise ExtractionContractError("catalog item is missing its ID or name")
            try:
                price = Decimal(raw_price)
            except InvalidOperation as error:
                raise ExtractionContractError("catalog item has an invalid price") from error
            records.append(CatalogRecord(item_id, name, price, self._page.url))
        return records
