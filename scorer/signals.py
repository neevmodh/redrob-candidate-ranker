"""
scorer/signals.py — Behavioral signal scorer (availability multiplier)

Converts the 23 Redrob platform signals into an availability/engagement
multiplier in range [0.50, 1.20] applied on top of the profile score.

Key insight from the JD:
  "A perfect-on-paper candidate who hasn't logged in for 6 months
   and has a 5% response rate is, for hiring purposes, not actually available."
"""

from __future__ import annotations
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _days_ago(d: date | None, reference: date | None = None) -> float:
    """Days between reference (default today) and d. Returns large number if unknown."""
    if d is None:
        return 365.0  # unknown = assume stale
    ref = reference or date.today()
    delta = (ref - d).days
    return max(0.0, float(delta))


# ---------------------------------------------------------------------------
# Individual signal scorers
# ---------------------------------------------------------------------------

def _recency_score(days: float) -> float:
    """Score how recently a candidate was active."""
    if days <= 7:
        return 1.00
    elif days <= 30:
        return 0.95
    elif days <= 60:
        return 0.85
    elif days <= 90:
        return 0.75
    elif days <= 180:
        return 0.55
    elif days <= 270:
        return 0.35
    else:
        return 0.15  # >9 months inactive — almost certainly not looking


def _response_time_score(avg_hours: float) -> float:
    if avg_hours <= 12:
        return 1.00
    elif avg_hours <= 24:
        return 0.90
    elif avg_hours <= 48:
        return 0.80
    elif avg_hours <= 72:
        return 0.70
    elif avg_hours <= 120:
        return 0.60
    elif avg_hours <= 168:
        return 0.50
    else:
        return 0.30


def _notice_period_score(days: int) -> float:
    """JD explicitly says: sub-30 preferred, can buy out up to 30 days."""
    if days <= 15:
        return 1.00
    elif days <= 30:
        return 0.95
    elif days <= 45:
        return 0.80
    elif days <= 60:
        return 0.70
    elif days <= 90:
        return 0.55
    elif days <= 120:
        return 0.40
    else:
        return 0.25  # 120+ days notice = hard to hire


def _github_signal(score: float) -> float:
    """
    GitHub activity score. -1 = no GitHub linked.
    The JD values open-source contributions.
    """
    if score < 0:
        return 0.30  # no GitHub — neutral-negative
    elif score == 0:
        return 0.35
    elif score <= 20:
        return 0.55
    elif score <= 50:
        return 0.75
    elif score <= 80:
        return 0.90
    else:
        return 1.00


def _offer_acceptance_signal(rate: float) -> float:
    """
    Offer acceptance rate. -1 = no prior offer history.
    High rate = candidate follows through.
    """
    if rate < 0:
        return 0.60  # no history — neutral
    elif rate >= 0.80:
        return 1.00
    elif rate >= 0.60:
        return 0.85
    elif rate >= 0.40:
        return 0.70
    elif rate >= 0.20:
        return 0.55
    else:
        return 0.40


# ---------------------------------------------------------------------------
# Main behavioral scorer
# ---------------------------------------------------------------------------

def compute_behavioral_score(candidate: dict) -> dict:
    """
    Compute the behavioral availability multiplier for a candidate.

    Returns dict:
        multiplier   float [0.50, 1.20]
        breakdown    dict of sub-scores
    """
    signals: dict = candidate.get("redrob_signals", {})
    if not signals:
        return {"multiplier": 0.70, "breakdown": {}}

    # ---- Availability (most important) --------------------------------
    open_to_work = bool(signals.get("open_to_work_flag", False))
    last_active = _parse_date(signals.get("last_active_date"))
    days_since_active = _days_ago(last_active)
    recency = _recency_score(days_since_active)

    # open_to_work is a strong binary signal
    open_bonus = 0.20 if open_to_work else 0.0
    availability_score = min(1.0, recency * 0.80 + open_bonus)

    # ---- Responsiveness -----------------------------------------------
    response_rate = float(signals.get("recruiter_response_rate") or 0)
    avg_response_hours = float(signals.get("avg_response_time_hours") or 168)
    interview_rate = float(signals.get("interview_completion_rate") or 0.5)

    resp_time = _response_time_score(avg_response_hours)
    responsiveness = (
        0.50 * response_rate +
        0.30 * resp_time +
        0.20 * interview_rate
    )

    # ---- Notice period ------------------------------------------------
    notice_days = int(signals.get("notice_period_days") or 90)
    notice_fit = _notice_period_score(notice_days)

    # ---- Profile quality signals --------------------------------------
    completeness = float(signals.get("profile_completeness_score") or 50) / 100.0
    verified_email = 0.05 if signals.get("verified_email") else 0.0
    verified_phone = 0.05 if signals.get("verified_phone") else 0.0
    linkedin = 0.03 if signals.get("linkedin_connected") else 0.0

    github_raw = float(signals.get("github_activity_score") if
                       signals.get("github_activity_score") is not None else -1)
    github_sig = _github_signal(github_raw)

    saved_30d = int(signals.get("saved_by_recruiters_30d") or 0)
    # Being saved by recruiters = social proof
    saved_signal = min(0.10, saved_30d * 0.01)

    offer_rate = float(signals.get("offer_acceptance_rate")
                       if signals.get("offer_acceptance_rate") is not None else -1)
    offer_sig = _offer_acceptance_signal(offer_rate)

    profile_quality = min(1.0,
        completeness * 0.35 +
        verified_email +
        verified_phone +
        linkedin +
        github_sig * 0.25 +
        saved_signal +
        offer_sig * 0.20
    )

    # ---- Combine into raw multiplier ---------------------------------
    raw = (
        0.40 * availability_score +
        0.30 * responsiveness +
        0.15 * notice_fit +
        0.15 * profile_quality
    )

    # Map [0, 1] → [0.50, 1.20]
    multiplier = 0.50 + raw * 0.70

    # Hard floor: if completely inactive AND not open_to_work → cap at 0.65
    if not open_to_work and days_since_active > 270:
        multiplier = min(multiplier, 0.62)

    # Soft boost: very high response rate + open_to_work = premium
    if open_to_work and response_rate >= 0.80 and days_since_active <= 30:
        multiplier = min(1.20, multiplier + 0.08)

    multiplier = max(0.50, min(1.20, multiplier))

    return {
        "multiplier": round(multiplier, 4),
        "breakdown": {
            "availability": round(availability_score, 3),
            "responsiveness": round(responsiveness, 3),
            "notice_fit": round(notice_fit, 3),
            "profile_quality": round(profile_quality, 3),
            "open_to_work": open_to_work,
            "days_since_active": round(days_since_active, 0),
            "response_rate": response_rate,
            "notice_days": notice_days,
            "github_score": github_raw,
        },
    }
