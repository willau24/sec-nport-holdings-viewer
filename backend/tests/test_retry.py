import httpx
import pytest

from nport import config
from nport.edgar import EdgarClient
from nport.errors import EdgarRateLimited, EdgarUnavailable

def client_returning(*statuses: int) -> tuple[EdgarClient, list[int]]:
    attempts: list[int] = []
    sequence = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(len(attempts) + 1)
        code = sequence[min(len(attempts) - 1, len(sequence) - 1)]
        return httpx.Response(code, json={"ok": True})

    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return EdgarClient(inner), attempts

class TestRateLimitFailsFast:
    async def test_429_is_not_retried(self):
        edgar, attempts = client_returning(429)
        async with edgar:
            with pytest.raises(EdgarRateLimited):
                await edgar.fetch_submissions("0000884394")
        assert len(attempts) == 1

class TestServerErrorsAreRetried:
    async def test_503_retries_to_the_limit(self):
        edgar, attempts = client_returning(503)
        async with edgar:
            with pytest.raises(EdgarUnavailable):
                await edgar.fetch_submissions("0000884394")
        assert len(attempts) == config.MAX_RETRIES

    async def test_recovers_when_a_retry_succeeds(self):
        edgar, attempts = client_returning(503, 200)
        async with edgar:
            body = await edgar.fetch_submissions("0000884394")
        assert body == {"ok": True}
        assert len(attempts) == 2

class TestTimeouts:
    @pytest.mark.parametrize(
        "error",
        [httpx.ConnectTimeout("timed out"), httpx.ConnectError("refused")],
    )
    async def test_network_failures_are_retried_then_reported(self, error):
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            raise error

        inner = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with EdgarClient(inner) as edgar:
            with pytest.raises(EdgarUnavailable):
                await edgar.fetch_submissions("0000884394")
        assert len(attempts) == config.MAX_RETRIES


class TestConcurrencyLimit:
    async def test_never_exceeds_the_configured_ceiling(self):
        import asyncio

        active = 0
        peak = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return httpx.Response(200, json={})

        inner = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with EdgarClient(inner) as edgar:
            await asyncio.gather(
                *(
                    edgar.fetch_document(f"https://example.test/{i}.xml")
                    for i in range(20)
                )
            )
        assert peak <= config.MAX_CONCURRENT_REQUESTS
