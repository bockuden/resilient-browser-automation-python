"""Browser-based login and bounded reauthentication for protected targets."""

from __future__ import annotations

from urllib.parse import urlsplit

from playwright.async_api import Page, Response
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from resilient_browser_automation.errors import AuthenticationError


class BrowserAuthenticator:
    """Submit a target's login form without exposing credential values."""

    def __init__(
        self,
        username: str | None,
        password: str | None,
        *,
        max_attempts: int = 2,
        timeout_ms: int = 10_000,
    ) -> None:
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        self._username = username
        self._password = password
        self._max_attempts = max_attempts
        self._timeout_ms = timeout_ms
        self._attempts = 0

    async def authenticate_if_required(self, page: Page) -> None:
        """Authenticate if the current browser location is a login form."""

        if not _is_login_page(page.url):
            return
        if self._username is None or self._password is None:
            raise AuthenticationError("target requires authentication but credentials are unset")
        if self._attempts >= self._max_attempts:
            raise AuthenticationError("authentication attempt limit exceeded")
        self._attempts += 1

        form = page.locator("form[action='/login']")
        username = form.locator("input[name='username']")
        password = form.locator("input[name='password']")
        submit = form.locator("button[type='submit']")
        try:
            if (
                await form.count() != 1
                or await username.count() != 1
                or await password.count() != 1
                or await submit.count() != 1
            ):
                raise AuthenticationError("login page is missing required form controls")
            await username.fill(self._username, timeout=self._timeout_ms)
            await password.fill(self._password, timeout=self._timeout_ms)
            async with page.expect_response(
                _is_login_submission, timeout=self._timeout_ms
            ) as response_info:
                await submit.click(timeout=self._timeout_ms)
            response = await response_info.value
        except PlaywrightTimeoutError as error:
            raise AuthenticationError("login form did not complete before its timeout") from error

        if response.status == 401:
            raise AuthenticationError("invalid username or password")
        if response.status >= 400:
            raise AuthenticationError(f"login failed with HTTP {response.status}")
        if _is_login_page(page.url):
            raise AuthenticationError("login did not return to the requested catalog page")


def _is_login_page(url: str) -> bool:
    try:
        return urlsplit(url).path.rstrip("/") == "/login"
    except ValueError:
        return False


def _is_login_submission(response: Response) -> bool:
    if response.request.method.upper() != "POST":
        return False
    try:
        return urlsplit(response.url).path.rstrip("/") == "/login"
    except ValueError:
        return False
