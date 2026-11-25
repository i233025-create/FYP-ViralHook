"""
billing.py — Plans, usage metering, credit checks and subscriptions.

  Credit check   `metered("script" | "render" | "research")` is a FastAPI
                 dependency: it answers 402 with a clear reason when the plan's
                 limit for this period is used up, otherwise returns a Meter;
                 the endpoint calls meter.charge() once the job is accepted and
                 meter.refund() (or refund_usage()) if it fails, so failures
                 never cost a credit.
  Periods        Free: the calendar month (UTC). Paid: the subscription's
                 period; a period that ended rolls on (renewal) unless the user
                 cancelled, in which case they drop back to Free.
  Checkout       POST /billing/checkout → a CheckoutSession + the provider's
                 hosted checkout URL (payments.py). The provider's webhook — or,
                 with the demo provider, POST /billing/demo/complete — marks it
                 paid and activates the plan. Paying needs a verified email.

Routes:
  GET  /billing/plans                   (public)  all plans with prices, limits, features
  GET  /billing/me                      plan, period, usage per meter, subscription
  GET  /billing/usage                   recent usage events
  POST /billing/checkout                {plan, interval, currency} → {sessionId, url}
  GET  /billing/checkout/{session_id}   status of a checkout (for the result page)
  POST /billing/demo/complete           {sessionId, outcome: paid|failed}   demo provider only
  POST /billing/cancel                  cancel at the end of the period
  POST /billing/resume                  undo a pending cancel
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_verified, settings_dep
from backend.config import Settings
from backend.db import get_db, get_sessionmaker
from backend.models import CheckoutSession, Subscription, UsageEvent, User, utcnow
from backend.payments import PaymentProvider, get_provider
from backend.plans import DEFAULT_PLAN, INTERVALS, METER_LABELS, METERED, PAID_PLANS, PLANS, Plan
from backend.security import as_utc

router = APIRouter(prefix="/billing", tags=["billing"])
PERIOD_DAYS = {"month": 30, "year": 365}


# ─── Account state ────────────────────────────────────────────────────────────

@dataclass
class Account:
    plan: Plan
    period_start: datetime
    period_end: datetime
    subscription: Subscription | None


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def account(db: Session, user: User, now: datetime | None = None) -> Account:
    """The user's plan and current period. Rolls an ended paid period forward."""
    now = now or utcnow()
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if sub is not None and sub.status != "canceled":
        end = as_utc(sub.current_period_end)
        if end <= now:
            if sub.cancel_at_period_end:
                sub.status = "canceled"
            else:  # renewal (a real provider confirms it by webhook; the demo renews itself)
                days = PERIOD_DAYS.get(sub.interval, 30)
                while end <= now:
                    sub.current_period_start, end = end, end + timedelta(days=days)
                sub.current_period_end = end
            db.commit()
        if sub.status != "canceled":
            return Account(PLANS[sub.plan], as_utc(sub.current_period_start), as_utc(sub.current_period_end), sub)
    start, end = _month_bounds(now)
    return Account(PLANS[DEFAULT_PLAN], start, end, sub if sub is not None and sub.status == "canceled" else None)


def used(db: Session, user_id: str, meter: str, since: datetime) -> int:
    return db.scalar(select(func.count()).select_from(UsageEvent)
                     .where(UsageEvent.user_id == user_id, UsageEvent.meter == meter, UsageEvent.at >= since)) or 0


def usage_summary(db: Session, user: User, acct: Account) -> dict:
    out = {}
    for m in METERED:
        limit = acct.plan.limit(m)
        n = used(db, user.id, m, acct.period_start)
        out[m] = {"used": n, "limit": limit, "remaining": None if limit is None else max(0, limit - n)}
    return out


# ─── Credit check (dependency) ────────────────────────────────────────────────

class Meter:
    def __init__(self, db: Session, user_id: str, meter: str):
        self.db, self.user_id, self.meter = db, user_id, meter
        self.event_id: str | None = None

    def charge(self, note: str = "") -> str:
        event = UsageEvent(user_id=self.user_id, meter=self.meter, note=note[:255])
        self.db.add(event)
        self.db.commit()
        self.event_id = event.id
        return event.id

    def refund(self) -> None:
        if self.event_id:
            refund_usage(self.event_id, self.db)
            self.event_id = None

    def refund_later(self):
        """A callable that refunds this charge later, e.g. from a background job.
        It opens its own session on the SAME database as this request."""
        event_id, bind = self.event_id, self.db.get_bind()

        def refund() -> None:
            if event_id:
                with Session(bind=bind) as db:
                    refund_usage(event_id, db)
        return refund


def refund_usage(event_id: str, db: Session | None = None) -> None:
    """Undo one charge (a job that failed). Works from background threads too."""
    own = db is None
    db = db or get_sessionmaker()()
    try:
        db.execute(delete(UsageEvent).where(UsageEvent.id == event_id))
        db.commit()
    finally:
        if own:
            db.close()


def metered(meter: str):
    """Dependency factory: 402 if this period's limit is used up, else a Meter."""
    assert meter in METERED

    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Meter:
        acct = account(db, user)
        limit = acct.plan.limit(meter)
        if limit is not None:
            n = used(db, user.id, meter, acct.period_start)
            if n >= limit:
                what = METER_LABELS[meter]
                message = (f"Your {acct.plan.name} plan doesn't include {what}." if limit == 0
                           else f"You've used all {limit} {what} for this period.")
                raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, {
                    "message": message, "code": "out_of_credits", "meter": meter, "plan": acct.plan.id,
                    "limit": limit, "used": n, "resetsAt": acct.period_end.isoformat(),
                })
        return Meter(db, user.id, meter)

    return dependency


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CheckoutIn(BaseModel):
    plan: str
    interval: str = "month"
    currency: str = "PKR"


class DemoCompleteIn(BaseModel):
    sessionId: str
    outcome: str = "paid"   # paid | failed


def _sub_out(sub: Subscription | None) -> dict | None:
    if sub is None:
        return None
    return {"plan": sub.plan, "interval": sub.interval, "status": sub.status,
            "currentPeriodEnd": as_utc(sub.current_period_end).isoformat(),
            "cancelAtPeriodEnd": sub.cancel_at_period_end, "provider": sub.provider}


def provider_dep() -> PaymentProvider:
    return get_provider()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/plans")
def plans():
    return {"plans": [p.public() for p in PLANS.values()], "currencies": ["PKR", "USD"], "intervals": list(INTERVALS)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db),
       provider: PaymentProvider = Depends(provider_dep)):
    acct = account(db, user)
    return {
        "plan": acct.plan.public(),
        "period": {"start": acct.period_start.isoformat(), "end": acct.period_end.isoformat()},
        "usage": usage_summary(db, user, acct),
        "subscription": _sub_out(acct.subscription),
        "demoPayments": provider.is_demo,
    }


@router.get("/usage")
def usage(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(UsageEvent).where(UsageEvent.user_id == user.id)
                      .order_by(UsageEvent.at.desc()).limit(max(1, min(limit, 200)))).all()
    return {"events": [{"meter": r.meter, "at": as_utc(r.at).isoformat(), "note": r.note} for r in rows]}


@router.post("/checkout")
def checkout(body: CheckoutIn, user: User = Depends(require_verified), db: Session = Depends(get_db),
             settings: Settings = Depends(settings_dep), provider: PaymentProvider = Depends(provider_dep)):
    if body.plan not in PAID_PLANS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a paid plan.")
    if body.interval not in INTERVALS or body.currency not in ("PKR", "USD"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown billing interval or currency.")
    acct = account(db, user)
    if acct.plan.id == body.plan and acct.subscription and not acct.subscription.cancel_at_period_end:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You're already on {acct.plan.name}.")
    plan = PLANS[body.plan]
    amount = plan.public()["prices"][body.currency][body.interval]
    session = CheckoutSession(user_id=user.id, plan=plan.id, interval=body.interval, currency=body.currency,
                              amount=amount, provider=provider.name)
    db.add(session)
    db.commit()
    link = provider.checkout_url(session.id, settings)
    return {"sessionId": session.id, "url": link.url, "provider": link.provider, "demo": provider.is_demo}


@router.get("/checkout/{session_id}")
def checkout_status(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(CheckoutSession, session_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown checkout.")
    return {"sessionId": s.id, "status": s.status, "plan": s.plan, "interval": s.interval,
            "currency": s.currency, "amount": s.amount}


def complete_checkout(db: Session, s: CheckoutSession, paid: bool) -> None:
    """What a provider webhook does: mark the session and (if paid) activate the plan."""
    if s.status != "open":
        return  # webhooks can repeat; only the first one counts
    s.status, s.completed_at = ("paid" if paid else "failed"), utcnow()
    if paid:
        now = utcnow()
        sub = db.scalar(select(Subscription).where(Subscription.user_id == s.user_id))
        if sub is None:
            sub = Subscription(user_id=s.user_id, plan=s.plan, current_period_start=now,
                               current_period_end=now + timedelta(days=PERIOD_DAYS[s.interval]))
            db.add(sub)
        sub.plan, sub.interval, sub.status, sub.provider = s.plan, s.interval, "active", s.provider
        sub.current_period_start, sub.current_period_end = now, now + timedelta(days=PERIOD_DAYS[s.interval])
        sub.cancel_at_period_end = False
    db.commit()


@router.post("/demo/complete")
def demo_complete(body: DemoCompleteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
                  provider: PaymentProvider = Depends(provider_dep)):
    if not provider.is_demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not available.")
    s = db.get(CheckoutSession, body.sessionId)
    if s is None or s.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown checkout.")
    complete_checkout(db, s, paid=body.outcome == "paid")
    return {"status": s.status}


@router.post("/cancel")
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acct = account(db, user)
    if acct.subscription is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You're on the Free plan.")
    acct.subscription.cancel_at_period_end = True
    db.commit()
    return {"subscription": _sub_out(acct.subscription)}


@router.post("/resume")
def resume(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acct = account(db, user)
    if acct.subscription is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You're on the Free plan.")
    acct.subscription.cancel_at_period_end = False
    db.commit()
    return {"subscription": _sub_out(acct.subscription)}


@router.post("/webhook/{provider_name}")
async def webhook(provider_name: str, request: Request):
    """Real providers post here once one is chosen; verified per provider in payments.py."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"No webhook handler for {provider_name!r} yet.")
