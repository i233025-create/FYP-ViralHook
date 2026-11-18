"""
payments.py — The payment provider behind one small interface.

Only this file changes when a real provider is chosen (Safepay, Paddle, Lemon
Squeezy…): it creates a hosted checkout and turns the provider's webhook into
"this checkout was paid / failed". Everything else (plans, limits, usage,
subscriptions) lives in billing.py and does not care which provider is used.

PAYMENT_PROVIDER=demo (default) is a stand-in with NO real money and NO real
gateway: checkout opens our own demo page, where the user picks "pay" or
"fail", which completes the session the way a webhook would.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from backend.config import Settings


@dataclass
class CheckoutLink:
    url: str              # where the browser goes to pay
    provider: str


class PaymentProvider(Protocol):
    name: str
    is_demo: bool

    def checkout_url(self, session_id: str, settings: Settings) -> CheckoutLink: ...


class DemoProvider:
    """No real payments: the frontend's /checkout/demo page plays the provider."""
    name = "demo"
    is_demo = True

    def checkout_url(self, session_id: str, settings: Settings) -> CheckoutLink:
        return CheckoutLink(url=f"{settings.frontend_url}/checkout/demo?session={session_id}", provider=self.name)


def get_provider() -> PaymentProvider:
    name = os.getenv("PAYMENT_PROVIDER", "demo").strip().lower()
    if name == "demo":
        return DemoProvider()
    raise RuntimeError(f"PAYMENT_PROVIDER={name!r} is not implemented yet (use 'demo')")
