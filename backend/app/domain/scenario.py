"""Fictional, deterministic scenario data for the two demo tenants.

Nothing here is real customer data and nothing is random: every number is derived from the tables below and from
`today`, so the same date always gives the same answers (tests rely on this). A real deployment would read these
from the customer's planning systems instead.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

# ----------------------------------------------------------------------------- Northwind Grocers (retail)
SKUS = {
    "SKU-1001": {"name": "Whole Milk 1L", "daily": 420},
    "SKU-1002": {"name": "Free-range Eggs 12pk", "daily": 260},
    "SKU-1003": {"name": "Sourdough Loaf", "daily": 180},
    "SKU-1004": {"name": "Bananas 1kg", "daily": 350},
    "SKU-1005": {"name": "Orange Juice 1L", "daily": 240},
    "SKU-1006": {"name": "Pasta 500g", "daily": 150},
    "SKU-1007": {"name": "Frozen Pizza", "daily": 90},
    "SKU-1008": {"name": "Greek Yogurt 500g", "daily": 200},
}
LOCATIONS = {"DC-1": "Central DC", "DC-2": "East DC", "DC-5": "West DC"}
LOCATION_SHARE = {"DC-1": 0.45, "DC-2": 0.30, "DC-5": 0.25}
# Days of cover on hand per SKU and DC. The interesting cases are deliberate: milk and bananas are short at DC-5,
# pasta and yogurt are heavy at DC-2, so rebalancing has something real to do.
COVER_DAYS = {
    "SKU-1001": {"DC-1": 6.0, "DC-2": 7.5, "DC-5": 2.1},
    "SKU-1002": {"DC-1": 7.0, "DC-2": 6.0, "DC-5": 5.5},
    "SKU-1003": {"DC-1": 2.5, "DC-2": 2.0, "DC-5": 2.2},
    "SKU-1004": {"DC-1": 4.0, "DC-2": 3.5, "DC-5": 1.5},
    "SKU-1005": {"DC-1": 9.0, "DC-2": 10.0, "DC-5": 8.0},
    "SKU-1006": {"DC-1": 22.0, "DC-2": 41.0, "DC-5": 18.0},
    "SKU-1007": {"DC-1": 15.0, "DC-2": 14.0, "DC-5": 13.0},
    "SKU-1008": {"DC-1": 10.0, "DC-2": 26.0, "DC-5": 9.0},
}
WEEKDAY_FACTOR = [0.95, 0.92, 0.95, 1.0, 1.08, 1.22, 1.10]  # Monday..Sunday
PROMOS = {"SKU-1007": {"from_day": 3, "to_day": 9, "uplift": 0.35, "label": "Weekend pizza promotion"}}
TARGET_COVER_DAYS = 7.0  # what the planner aims to hold; below this is "short"
EXCESS_COVER_DAYS = 21.0  # above this is "excess"

# ----------------------------------------------------------------------------- Harbor Freight Lines (logistics)
LANES = {
    "Chicago-Dallas": {"origin": "Chicago", "destination": "Dallas", "miles": 925},
    "Atlanta-Miami": {"origin": "Atlanta", "destination": "Miami", "miles": 660},
    "Denver-Phoenix": {"origin": "Denver", "destination": "Phoenix", "miles": 940},
    "Seattle-Portland": {"origin": "Seattle", "destination": "Portland", "miles": 175},
}
# (id, lane, carrier, days until planned arrival, hours of delay, reason, cargo value USD, SLA slack hours)
_SHIPMENTS = [
    ("SHP-4101", "Chicago-Dallas", "Redline Carriers", 1, 14, "Winter storm in Missouri", 84000, 6),
    ("SHP-4102", "Chicago-Dallas", "Redline Carriers", 2, 0, None, 41000, 12),
    ("SHP-4103", "Atlanta-Miami", "Gulfstream Haul", 1, 9, "Driver hours-of-service limit", 56000, 4),
    ("SHP-4104", "Atlanta-Miami", "Gulfstream Haul", 3, 0, None, 23000, 24),
    ("SHP-4105", "Denver-Phoenix", "Summit Freight", 2, 20, "Mountain pass closure", 112000, 8),
    ("SHP-4106", "Denver-Phoenix", "Summit Freight", 4, 3, "Yard congestion", 37000, 12),
    ("SHP-4107", "Seattle-Portland", "Cascade Line", 1, 0, None, 18000, 6),
    ("SHP-4108", "Seattle-Portland", "Cascade Line", 5, 2, "Terminal queue", 29000, 10),
    ("SHP-4109", "Chicago-Dallas", "Prairie Express", 6, 0, None, 66000, 18),
    ("SHP-4110", "Atlanta-Miami", "Gulfstream Haul", 8, 12, "Port congestion at Miami", 91000, 6),
]
# mode -> (cost USD per mile, kg CO2e per mile, miles per day)
MODES = {
    "Truckload": (2.10, 1.05, 550),
    "Intermodal rail": (1.35, 0.32, 380),
    "Expedited team truck": (3.40, 1.30, 900),
}


@dataclass(frozen=True)
class AsOf:
    """When the data is considered current. Fixed to 06:00 UTC on `today` so answers can state a precise time."""

    today: date

    def iso(self) -> str:
        return datetime.combine(self.today, time(6, 0), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# ----------------------------------------------------------------------------- derived data
def inventory_rows(sku: str | None = None, location: str | None = None) -> list[dict]:
    rows = []
    for s, info in SKUS.items():
        for loc, share in LOCATION_SHARE.items():
            if (sku and s != sku) or (location and loc != location):
                continue
            daily = info["daily"] * share
            on_hand = round(COVER_DAYS[s][loc] * daily)
            rows.append(
                {
                    "sku": s,
                    "name": info["name"],
                    "location": loc,
                    "on_hand": on_hand,
                    "daily_demand": round(daily),
                    "days_of_cover": round(on_hand / daily, 1),
                }
            )
    return rows


def forecast_series(sku: str, today: date, history_days: int = 14, horizon_days: int = 14) -> list[dict]:
    """Daily network demand: `history_days` back (forecast and actual) and `horizon_days` ahead (forecast only)."""
    base = SKUS[sku]["daily"]
    seed = int(sku[-4:])
    promo = PROMOS.get(sku)
    points = []
    for offset in range(-history_days, horizon_days):
        day = today + timedelta(days=offset)
        factor = WEEKDAY_FACTOR[day.weekday()]
        if promo and promo["from_day"] <= offset <= promo["to_day"]:
            factor *= 1 + promo["uplift"]
        forecast = round(base * factor)
        point = {"date": day.isoformat(), "forecast": forecast}
        if offset < 0:
            # Actuals wobble around the forecast by up to ~7%, deterministically.
            point["actual"] = round(forecast * (1 + 0.07 * math.sin(offset * 1.7 + seed)))
        points.append(point)
    return points


def shipments(today: date) -> list[dict]:
    rows = []
    for sid, lane, carrier, days, delay_h, reason, value, slack_h in _SHIPMENTS:
        planned = datetime.combine(today + timedelta(days=days), time(12, 0), tzinfo=timezone.utc)
        sla_due = planned + timedelta(hours=slack_h)
        current = planned + timedelta(hours=delay_h)
        hours_late = (current - sla_due).total_seconds() / 3600
        rows.append(
            {
                "id": sid,
                "lane": lane,
                "carrier": carrier,
                "planned_eta": _iso(planned),
                "current_eta": _iso(current),
                "sla_due": _iso(sla_due),
                "delay_hours": delay_h,
                "hours_past_sla": round(max(hours_late, 0), 1),
                "slack_hours_left": round(max(-hours_late, 0), 1),
                "reason": reason,
                "cargo_value_usd": value,
                "days_until_sla": days,
            }
        )
    return rows


def lane_options(lane: str) -> list[dict]:
    miles = LANES[lane]["miles"]
    return [
        {
            "mode": mode,
            "cost_usd": round(miles * cost_per_mile),
            "co2e_kg": round(miles * co2_per_mile),
            "transit_days": max(1, math.ceil(miles / miles_per_day)),
        }
        for mode, (cost_per_mile, co2_per_mile, miles_per_day) in MODES.items()
    ]
