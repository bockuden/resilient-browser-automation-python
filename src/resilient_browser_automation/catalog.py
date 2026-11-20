"""Browser-based extraction of a paginated catalog."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from resilient_browser_automation.errors import (
    ExtractionContractError,
    TransientTargetError,
)


@dataclass(frozen=True, slots=True)
class CatalogRecord:
    """One item observed in the browser, with its source page URL."""

    item_id: str
    name: str
    price: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class CatalogSelectors:
    """Target-provided test IDs and item ID attribute used by the adapter."""

    catalog: str = "catalog"
    item: str = "catalog-item"
    item_id_attribute: str = "data-item-id"
    item_name: str = "item-name"
    item_price: str = "item-price"
    next_page: str = "next-page"

    def __post_init__(self) -> None:
        if any(not value.strip() for value in self.__slots_values()):
            raise ValueError("catalog selector values must not be empty")

    def __slots_values(self) -> tuple[str, ...]:
        return (
            self.catalog,
            self.item,
            self.item_id_attribute,
            self.item_name,
            self.item_price,
            self.next_page,
        )


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

    def __init__(
        self,
        page: Page,
        *,
        selectors: CatalogSelectors = CatalogSelectors(),
        readiness_timeout_ms: int = 10_000,
    ) -> None:
        if readiness_timeout_ms <= 0:
            raise ValueError("readiness_timeout_ms must be positive")
        self._page = page
        self._selectors = selectors
        self._readiness_timeout_ms = readiness_timeout_ms

    async def extract(
        self,
        *,
        page_limit: int,
        on_page: Callable[[int, tuple[CatalogRecord, ...]], Awaitable[None]] | None = None,
    ) -> CatalogResult:
        """Read each loaded page and follow its next-page control."""

        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or page_limit <= 0:
            raise ValueError("page_limit must be a positive integer")

        records: list[CatalogRecord] = []
        page_number = 1
        while True:
            await self._wait_for_page(page_number)
            page_records = tuple(await self._read_records())
            records.extend(page_records)
            if on_page is not None:
                await on_page(page_number, page_records)
            next_page = self._page.get_by_test_id(self._selectors.next_page)
            next_count = await next_page.count()
            visible_controls = self._page.locator("nav button")
            control_count = await visible_controls.count()
            if next_count > 1:
                raise ExtractionContractError("catalog has multiple next-page controls")
            if next_count == 0:
                if control_count:
                    raise ExtractionContractError(
                        "catalog next-page control is missing its required marker"
                    )
                return CatalogResult(tuple(records), page_number, CatalogEndReason.NATURAL_END)
            if page_number == page_limit:
                return CatalogResult(tuple(records), page_number, CatalogEndReason.PAGE_LIMIT)

            try:
                await next_page.click()
            except PlaywrightTimeoutError as error:
                raise ExtractionContractError(
                    "catalog next-page control is not actionable"
                ) from error
            page_number += 1

    async def _wait_for_page(self, page_number: int) -> None:
        status = self._page.get_by_role("status")
        catalog = self._page.get_by_test_id(self._selectors.catalog)
        if await status.count() != 1 or await catalog.count() != 1:
            raise ExtractionContractError("catalog page is missing its status or catalog container")
        try:
            await status.wait_for(state="visible", timeout=self._readiness_timeout_ms)
            await self._page.wait_for_function(
                "([number]) => { const status = document.querySelector('[role=status]'); "
                "return status && (status.dataset.state === 'error' || "
                "(status.dataset.state === 'success' && "
                "status.textContent.includes(`Page ${number} loaded`))); }",
                arg=[page_number],
                timeout=self._readiness_timeout_ms,
            )
        except PlaywrightTimeoutError as error:
            raise TransientTargetError(
                f"catalog page {page_number} did not become ready in time"
            ) from error
        if await status.get_attribute("data-state") == "error":
            message = (await status.inner_text()).strip()
            raise TransientTargetError(message or f"catalog page {page_number} failed to load")

    async def _read_records(self) -> list[CatalogRecord]:
        catalog = self._page.get_by_test_id(self._selectors.catalog)
        items = catalog.get_by_test_id(self._selectors.item)
        if await items.count() == 0 and await catalog.locator(":scope > *").count() > 0:
            raise ExtractionContractError("catalog contains items without the required item marker")
        records: list[CatalogRecord] = []
        for index in range(await items.count()):
            item = items.nth(index)
            item_id = await item.get_attribute(self._selectors.item_id_attribute)
            name = await self._required_text(item, self._selectors.item_name, "name")
            raw_price = await self._required_text(item, self._selectors.item_price, "price")
            if not item_id or not name:
                raise ExtractionContractError("catalog item is missing its ID or name")
            try:
                price = Decimal(raw_price)
            except InvalidOperation as error:
                raise ExtractionContractError("catalog item has an invalid price") from error
            if not price.is_finite():
                raise ExtractionContractError("catalog item has an invalid price")
            records.append(CatalogRecord(item_id, name, price, self._page.url))
        return records

    async def _required_text(self, item: Locator, test_id: str, label: str) -> str:
        locator = item.get_by_test_id(test_id)
        if await locator.count() != 1:
            raise ExtractionContractError(f"catalog item is missing its {label} element")
        return (await locator.inner_text()).strip()
