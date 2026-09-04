"""HTTP layer. requests when it is installed, curl subprocess otherwise.

Neither is a hard requirement, which is what keeps this plugin install-free.

urllib is not used, because some Python builds ship an empty openssl
certificate directory (ssl.get_default_verify_paths().cafile is None) and then
fail with CERTIFICATE_VERIFY_FAILED. requests works there because certifi
carries its own bundle, and curl works because it uses the system trust store.
"""
from __future__ import annotations

import json
import subprocess
import time

TIMEOUT = 15
RETRIES = 3
_warned_fallback = False


class FetchError(RuntimeError):
    pass


def _via_curl(url: str):
    r = subprocess.run(
        ["curl", "-sS", "--max-time", str(TIMEOUT), url],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise FetchError(f"curl failed for {url}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def fetch_json(url: str):
    """GET url -> parsed JSON. Raises FetchError after RETRIES attempts."""
    global _warned_fallback
    last = None
    for attempt in range(RETRIES):
        try:
            import requests
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001 - fall back on anything
            last = e
            if e.__class__.__name__ in ("SSLError", "ImportError"):
                if not _warned_fallback:
                    print("  [info] requests unavailable, using curl")
                    _warned_fallback = True
                try:
                    return _via_curl(url)
                except Exception as ce:  # noqa: BLE001
                    last = ce
            if attempt < RETRIES - 1:
                time.sleep(0.4 * (attempt + 1))
    raise FetchError(f"{url}: {last}")
