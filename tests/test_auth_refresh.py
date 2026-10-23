import sys
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "oukitel"
sys.path.append(str(COMPONENT))

from auth_refresh import try_refresh_auth_key  # noqa: E402


class FakeClient:
    def __init__(
        self,
        *,
        key="old",
        token="token",
        device_key="dev",
        new_key="new",
        ok=True,
        error=None,
        change_device=False,
    ):
        self.auth_key = key
        self.access_token = token
        self.device_key = device_key
        self.new_key = new_key
        self.ok = ok
        self.error = error
        self.change_device = change_device
        self.calls = 0

    def fetch_device_info(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.change_device:
            self.device_key = "other-device"
        self.auth_key = self.new_key
        return self.ok


async def run_now(fn, *args):
    return fn(*args)


class AuthRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_refreshes_when_key_changes(self):
        client = FakeClient()
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertTrue(refreshed)
        self.assertEqual(key, "new")
        self.assertEqual(last, 1000.0)
        self.assertEqual(client.calls, 1)

    async def test_same_key_is_not_a_refresh(self):
        client = FakeClient(new_key="old")
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(key, "old")
        self.assertEqual(last, 1000.0)
        self.assertEqual(client.calls, 1)

    async def test_throttled_does_not_call_cloud(self):
        client = FakeClient()
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 900.0, 1000.0, run_now, min_interval=300.0
        )
        self.assertFalse(refreshed)
        self.assertEqual(key, "old")
        self.assertEqual(last, 900.0)
        self.assertEqual(client.calls, 0)

    async def test_no_access_token_does_not_call_cloud(self):
        client = FakeClient(token=None)
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(client.calls, 0)

    async def test_cloud_error_is_swallowed(self):
        client = FakeClient(error=RuntimeError("cloud down"))
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(key, "old")
        self.assertEqual(last, 1000.0)
        self.assertEqual(client.calls, 1)

    async def test_device_key_change_rejects_new_key(self):
        client = FakeClient(change_device=True)
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(key, "old")
        self.assertEqual(client.calls, 1)

    async def test_failure_is_throttled(self):
        client = FakeClient(error=RuntimeError("cloud down"))
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(client.calls, 1)
        # A second failure one second later must not hit the cloud again.
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", last, 1001.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(client.calls, 1)

    async def test_empty_new_key_is_rejected(self):
        client = FakeClient(new_key=None)
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(key, "old")

    async def test_fetch_false_is_rejected(self):
        client = FakeClient(ok=False)
        refreshed, key, last = await try_refresh_auth_key(
            client, "old", 0.0, 1000.0, run_now
        )
        self.assertFalse(refreshed)
        self.assertEqual(key, "old")


if __name__ == "__main__":
    unittest.main()

