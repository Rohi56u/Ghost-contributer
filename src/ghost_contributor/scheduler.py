from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import RepoPolicy
from .errors import SafeStop


def quiet(policy: RepoPolicy, instant: datetime | None = None) -> bool:
    local = (instant or datetime.now(timezone.utc)).astimezone(ZoneInfo(policy.timezone))
    current = local.strftime("%H:%M")
    start, end = policy.quiet_start, policy.quiet_end
    if start == end:
        return False
    return start <= current < end if start < end else current >= start or current < end


def period(policy: RepoPolicy, instant: datetime | None = None) -> str | None:
    local = (instant or datetime.now(timezone.utc)).astimezone(ZoneInfo(policy.timezone))
    if quiet(policy, local):
        return None
    # After downtime select the most recent calendar slot; never replay a backlog.
    day = local.date() if local.strftime("%H:%M") >= policy.at else local.date() - timedelta(days=1)
    return f"daily:{policy.timezone}:{day.isoformat()}:{policy.at}"


def serve(engine, interval: int = 30):
    while True:
        if not engine.state.flag("paused") and not engine.state.flag("killed"):
            for policy in engine.policies():
                key = period(policy)
                if key:
                    try:
                        engine.run(policy.name, task_period=key)
                    except SafeStop:
                        pass  # The run coordinator records controlled failure codes.
        time.sleep(interval)
