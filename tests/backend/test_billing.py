"""Billing: plans, credit checks (402), refunds, checkout with the demo provider, cancel/resume."""

from datetime import timedelta

import pytest

pytest.importorskip("httpx")

from sqlalchemy import select

from backend.billing import account, refund_usage
from backend.models import Subscription, UsageEvent, User, utcnow
from backend.plans import PLANS


def verify(client):
    """Mark the client's user as email-verified (checkout requires it)."""
    with client.Session() as db:
        db.get(User, client.user_id).email_verified_at = utcnow()
        db.commit()


def charge(client, meter, n):
    with client.Session() as db:
        for _ in range(n):
            db.add(UsageEvent(user_id=client.user_id, meter=meter))
        db.commit()


@pytest.fixture
def stub_agents(monkeypatch):
    """Research and scripting succeed instantly, no models needed."""
    import pipeline.agents.research_agent as ra
    import pipeline.agents.scripting_agent as sa

    monkeypatch.setattr(ra, "run_research", lambda profile, niche: {
        "trends": [{"topic": "x", "trend_score": 0.5, "creator_fit": 0.5, "data_summary": "", "why_trending": "",
                    "suggested_angle": "", "evidence": [], "low_confidence": False, "signals": []}],
        "queries": [], "error": None})
    calls = {"fail": False}

    def fake_variants(topic, trend=None, profile=None, paths=None):
        if calls["fail"]:
            raise RuntimeError("LLM down")
        return []
    monkeypatch.setattr(sa, "generate_variants", fake_variants)
    return calls


def test_public_plans_list():
    from fastapi.testclient import TestClient
    import server
    res = TestClient(server.app).get("/billing/plans")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()["plans"]]
    assert ids == ["free", "creator", "pro"]
    assert res.json()["plans"][1]["prices"]["PKR"]["month"] == PLANS["creator"].price_pkr_month


def test_me_shows_free_plan_and_usage(make_user_client):
    c = make_user_client("free@example.com", plan="free")
    charge(c, "script", 2)
    me = c.get("/billing/me").json()
    assert me["plan"]["id"] == "free" and me["subscription"] is None and me["demoPayments"] is True
    assert me["usage"]["script"] == {"used": 2, "limit": 5, "remaining": 3}
    assert me["usage"]["render"]["limit"] == 0


def test_free_plan_cannot_render(make_user_client, sample_production_plan):
    c = make_user_client("free@example.com", plan="free")
    res = c.post("/video/generate", json={"plan": sample_production_plan})
    assert res.status_code == 402
    detail = res.json()["detail"]
    assert detail["code"] == "out_of_credits" and detail["meter"] == "render" and "doesn't include" in detail["message"]


def test_limit_reached_returns_402_with_reset_date(make_user_client, stub_agents, tmp_path):
    from backend.workspace import workspace_for
    c = make_user_client("busy@example.com", plan="free")
    ws = workspace_for(c.user_id).ensure()
    ws.creator.text_profile.write_text("{}", encoding="utf-8")
    charge(c, "script", PLANS["free"].limit("script"))
    res = c.post("/script/generate", json={"topic": "kulfi"})
    assert res.status_code == 402
    assert res.json()["detail"]["resetsAt"] and res.json()["detail"]["used"] == 5


def test_success_charges_and_failure_does_not(make_user_client, stub_agents):
    from backend.workspace import workspace_for
    c = make_user_client("s@example.com", plan="free")
    workspace_for(c.user_id).ensure().creator.text_profile.write_text("{}", encoding="utf-8")
    assert c.post("/script/generate", json={"topic": "a"}).status_code == 200
    stub_agents["fail"] = True
    assert c.post("/script/generate", json={"topic": "b"}).status_code == 500
    assert c.get("/billing/me").json()["usage"]["script"]["used"] == 1
    assert c.post("/research/trends", json={"niche": "Food"}).status_code == 200
    assert c.get("/billing/me").json()["usage"]["research"]["used"] == 1


def test_refund_removes_the_charge(make_user_client):
    c = make_user_client("r@example.com", plan="pro")
    with c.Session() as db:
        ev = UsageEvent(user_id=c.user_id, meter="render")
        db.add(ev)
        db.commit()
        ev_id = ev.id
    refund_usage(ev_id, c.Session())
    assert c.get("/billing/me").json()["usage"]["render"]["used"] == 0


def test_checkout_needs_verified_email_and_a_paid_plan(make_user_client):
    c = make_user_client("pay@example.com", plan="free")
    assert c.post("/billing/checkout", json={"plan": "creator"}).status_code == 403
    verify(c)
    assert c.post("/billing/checkout", json={"plan": "free"}).status_code == 400
    assert c.post("/billing/checkout", json={"plan": "creator", "interval": "week"}).status_code == 400


def test_demo_checkout_upgrades_the_plan(make_user_client):
    c = make_user_client("up@example.com", plan="free")
    verify(c)
    res = c.post("/billing/checkout", json={"plan": "creator", "interval": "month", "currency": "PKR"})
    assert res.status_code == 200 and "/checkout/demo?session=" in res.json()["url"]
    sid = res.json()["sessionId"]
    assert c.get(f"/billing/checkout/{sid}").json()["status"] == "open"
    assert c.post("/billing/demo/complete", json={"sessionId": sid, "outcome": "paid"}).json()["status"] == "paid"
    me = c.get("/billing/me").json()
    assert me["plan"]["id"] == "creator" and me["usage"]["render"]["limit"] == 10
    # a repeated "webhook" changes nothing
    assert c.post("/billing/demo/complete", json={"sessionId": sid, "outcome": "failed"}).json()["status"] == "paid"


def test_failed_payment_keeps_the_old_plan(make_user_client):
    c = make_user_client("fail@example.com", plan="free")
    verify(c)
    sid = c.post("/billing/checkout", json={"plan": "pro"}).json()["sessionId"]
    c.post("/billing/demo/complete", json={"sessionId": sid, "outcome": "failed"})
    assert c.get("/billing/me").json()["plan"]["id"] == "free"


def test_other_users_cannot_see_or_complete_my_checkout(make_user_client):
    a = make_user_client("a@example.com", plan="free")
    verify(a)
    sid = a.post("/billing/checkout", json={"plan": "creator"}).json()["sessionId"]
    b = make_user_client("b@example.com", plan="free")
    assert b.get(f"/billing/checkout/{sid}").status_code == 404
    assert b.post("/billing/demo/complete", json={"sessionId": sid}).status_code == 404


def test_cancel_keeps_plan_until_period_end_then_free(make_user_client):
    c = make_user_client("c@example.com", plan="creator")
    assert c.post("/billing/cancel").json()["subscription"]["cancelAtPeriodEnd"] is True
    assert c.get("/billing/me").json()["plan"]["id"] == "creator"        # still paid until the end
    assert c.post("/billing/resume").json()["subscription"]["cancelAtPeriodEnd"] is False
    c.post("/billing/cancel")
    with c.Session() as db:                                               # jump past the period end
        sub = db.scalar(select(Subscription).where(Subscription.user_id == c.user_id))
        sub.current_period_end = utcnow() - timedelta(minutes=1)
        db.commit()
    assert c.get("/billing/me").json()["plan"]["id"] == "free"


def test_period_rolls_over_when_not_cancelled(make_user_client):
    c = make_user_client("roll@example.com", plan="pro")
    with c.Session() as db:
        sub = db.scalar(select(Subscription).where(Subscription.user_id == c.user_id))
        sub.current_period_start = utcnow() - timedelta(days=35)
        sub.current_period_end = utcnow() - timedelta(days=5)
        db.commit()
        user = db.get(User, c.user_id)
        acct = account(db, user)
    assert acct.plan.id == "pro" and acct.period_end > utcnow()


def test_free_period_is_the_calendar_month():
    from datetime import datetime, timezone
    from backend.billing import _month_bounds
    start, end = _month_bounds(datetime(2026, 12, 15, 10, tzinfo=timezone.utc))
    assert start == datetime(2026, 12, 1, tzinfo=timezone.utc) and end == datetime(2027, 1, 1, tzinfo=timezone.utc)
