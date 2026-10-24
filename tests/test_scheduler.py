from datetime import datetime, timezone

from ghost_contributor.config import RepoPolicy
from ghost_contributor.scheduler import period, quiet


def test_overnight_quiet_hours():
    p = RepoPolicy(name="test", path=".", timezone="UTC", at="10:00", quiet_start="22:00", quiet_end="08:00")
    assert quiet(p, datetime(2026,10,21,23,tzinfo=timezone.utc))
    assert quiet(p, datetime(2026,10,22,7,tzinfo=timezone.utc))
    assert not quiet(p, datetime(2026,10,22,8,tzinfo=timezone.utc))
    assert period(p, datetime(2026,10,22,7,tzinfo=timezone.utc)) is None


def test_coalesces_offline_slots():
    p = RepoPolicy(name="test",path=".",timezone="UTC",at="10:00",quiet_start="00:00",quiet_end="00:00")
    assert period(p,datetime(2026,10,21,9,tzinfo=timezone.utc)) == "daily:UTC:2026-10-20:10:00"
    assert period(p,datetime(2026,10,29,18,tzinfo=timezone.utc)) == "daily:UTC:2026-10-29:10:00"


def test_dst_fall_back_deduplicates_same_calendar_slot():
    p = RepoPolicy(name="test",path=".",timezone="America/New_York",at="01:15",quiet_start="00:00",quiet_end="00:00")
    a=period(p,datetime(2026,11,1,5,30,tzinfo=timezone.utc))
    b=period(p,datetime(2026,11,1,6,30,tzinfo=timezone.utc))
    assert a == b


def test_dst_spring_gap_runs_once_after_jump():
    p = RepoPolicy(name="test",path=".",timezone="America/New_York",at="02:30",quiet_start="00:00",quiet_end="00:00")
    assert period(p,datetime(2026,3,8,7,5,tzinfo=timezone.utc)) == "daily:America/New_York:2026-03-08:02:30"
