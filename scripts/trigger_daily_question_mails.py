"""Trigger the protected daily-question mail endpoint from a Railway Cron job."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    base_url = os.environ.get("T24_PUBLIC_BASE_URL", "").rstrip("/")
    token = os.environ.get("T24_DAILY_SCHEDULER_TOKEN", "")
    if not base_url or not token:
        print("T24_PUBLIC_BASE_URL and T24_DAILY_SCHEDULER_TOKEN are required.", file=sys.stderr)
        return 2
    request = Request(
        f"{base_url}/api/jobs/daily-question-mails",
        headers={"X-Cedz-Scheduler-Token": token, "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        print(f"Daily-question mail job failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
