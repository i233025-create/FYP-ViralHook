"""
plans.py — Subscription plans: prices, monthly limits and features, in one place.

Prices are PLACEHOLDERS until the team decides (2026-11-09); change them here
only. Limits reset every billing period (a calendar month for Free).

  limit None   = unlimited (fair use)
  limit 0      = not included in the plan
"""

from __future__ import annotations

from dataclasses import dataclass, field

# What can be metered. Each successful job of this kind uses one credit.
METERED = ("script", "render", "research")

METER_LABELS = {
    "script": "script generations",
    "render": "video renders",
    "research": "research runs",
}


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    tagline: str
    price_pkr_month: int
    price_usd_month: int
    price_pkr_year: int
    price_usd_year: int
    limits: dict = field(default_factory=dict)     # meter → per-period limit (None = unlimited)
    features: dict = field(default_factory=dict)   # feature → bool / int
    highlight: bool = False                        # "most popular" on the pricing page

    def limit(self, meter: str) -> int | None:
        return self.limits.get(meter, 0)

    def public(self) -> dict:
        return {
            "id": self.id, "name": self.name, "tagline": self.tagline, "highlight": self.highlight,
            "prices": {
                "PKR": {"month": self.price_pkr_month, "year": self.price_pkr_year},
                "USD": {"month": self.price_usd_month, "year": self.price_usd_year},
            },
            "limits": dict(self.limits),
            "features": dict(self.features),
        }


PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free", name="Free", tagline="Try ViralHook with your own style",
        price_pkr_month=0, price_usd_month=0, price_pkr_year=0, price_usd_year=0,
        limits={"script": 5, "render": 0, "research": 3},
        features={"xml_export": True, "creator_photos": False, "publish": False, "schedule": False, "profiles": 1},
    ),
    "creator": Plan(
        id="creator", name="Creator", tagline="For creators posting every week",
        price_pkr_month=1999, price_usd_month=9, price_pkr_year=19990, price_usd_year=90,
        limits={"script": 50, "render": 10, "research": 30},
        features={"xml_export": True, "creator_photos": True, "publish": True, "schedule": False, "profiles": 1},
        highlight=True,
    ),
    "pro": Plan(
        id="pro", name="Pro", tagline="For daily posting and small teams",
        price_pkr_month=4999, price_usd_month=19, price_pkr_year=49990, price_usd_year=190,
        limits={"script": None, "render": 40, "research": 100},
        features={"xml_export": True, "creator_photos": True, "publish": True, "schedule": True, "profiles": 3},
    ),
}

DEFAULT_PLAN = "free"
PAID_PLANS = tuple(p for p in PLANS if p != DEFAULT_PLAN)
INTERVALS = ("month", "year")
