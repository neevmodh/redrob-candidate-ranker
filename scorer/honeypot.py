"""
scorer/honeypot.py — Honeypot candidate detection

The dataset contains ~80 honeypot candidates with subtly impossible profiles:
  - Expert proficiency in many skills with 0 months of use
  - More work experience at a company than the company has existed
  - Implausibly long cumulative career tenure

Honeypots are forced to relevance tier 0 in the ground truth.
Submissions with >10% honeypots in top-100 are disqualified.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Known young companies with max-plausible tenure in months.
# Dataset reference date is approximately mid-2026 based on last_active_date
# values seen. Founding dates are verified against public records.
#
# Format: company_name_lower -> max_plausible_months_of_tenure
# Any candidate claiming MORE than this at that company is a honeypot.
# ---------------------------------------------------------------------------
YOUNG_COMPANY_MAX_MONTHS: dict[str, int] = {
    # Sarvam AI — founded April 2023. Max plausible as of mid-2026 = ~38mo
    "sarvam ai": 38,
    "sarvam": 38,

    # Krutrim — founded December 2023. Max plausible as of mid-2026 = ~30mo
    "krutrim": 30,

    # Rephrase.ai — founded 2019. Max plausible ~84mo (7 years). No honeypot risk.
    # Removing from list — too old to trigger false honeypot

    # Saarthi.ai — founded 2019. Same — removing, too old.

    # Locobuzz — founded 2015 — definitely not a honeypot signal.
}

# Legacy alias — kept for backward compat but no longer used in logic
YOUNG_COMPANIES = {k: 2023 for k in YOUNG_COMPANY_MAX_MONTHS}
_RECENT_FOUNDING_YEAR = 2022
_MAX_PLAUSIBLE_MONTHS_AT_RECENT_CO = 36


def _proficiency_value(p: str) -> int:
    return {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}.get(
        p.lower(), 0
    )


def _is_honeypot(candidate: dict) -> tuple[bool, str]:
    """
    Return (is_honeypot, reason).

    Strategy: one STRONG signal is enough to flag a honeypot if it is
    clearly impossible (impossible company tenure, inflated career math).
    Weaker signals (expert count, zero-duration skills) require 2+.
    """
    flags: list[str] = []
    strong_flags: list[str] = []   # single strong flag = instant honeypot

    skills: list[dict] = candidate.get("skills", [])
    career: list[dict] = candidate.get("career_history", [])
    profile: dict = candidate.get("profile", {})

    # ------------------------------------------------------------------
    # STRONG Signal 1: Impossible company tenure
    # Candidate claims to have worked at a company longer than the company
    # has plausibly existed as of the dataset reference date (~mid-2026).
    # ------------------------------------------------------------------
    for role in career:
        company_lower = role.get("company", "").lower().strip()
        duration = int(role.get("duration_months") or 0)

        for known_co, max_months in YOUNG_COMPANY_MAX_MONTHS.items():
            if known_co in company_lower and duration > max_months:
                strong_flags.append(
                    f"impossible-tenure: {role.get('company')} "
                    f"({duration}mo claimed, max plausible {max_months}mo)"
                )
                break

    # ------------------------------------------------------------------
    # STRONG Signal 2: Inflated total career tenure vs stated YoE
    # Total months across all roles >> 2.5× expected (major fabrication).
    # ------------------------------------------------------------------
    yoe = float(profile.get("years_of_experience") or 0)
    total_career_months = sum(int(r.get("duration_months") or 0) for r in career)
    if yoe > 0 and total_career_months > (yoe * 12 * 2.5):
        strong_flags.append(
            f"inflated-tenure: {total_career_months}mo vs "
            f"{yoe * 12:.0f}mo expected from YoE ({total_career_months/(yoe*12):.1f}x)"
        )

    # ------------------------------------------------------------------
    # Weak Signal 1: Expert skill with 0 months used (1+ is suspicious,
    # use as strong signal if combined with anything, or alone if 3+)
    # ------------------------------------------------------------------
    zero_month_experts = [
        s["name"]
        for s in skills
        if _proficiency_value(s.get("proficiency", "")) >= 4
        and int(s.get("duration_months") or 0) == 0
    ]
    if len(zero_month_experts) >= 3:
        # 3+ expert skills with 0 months = strong signal on its own
        strong_flags.append(
            f"expert-0month({len(zero_month_experts)}): {', '.join(zero_month_experts[:3])}"
        )
    elif len(zero_month_experts) >= 1:
        flags.append(f"expert-0month({len(zero_month_experts)}): {', '.join(zero_month_experts[:3])}")

    # ------------------------------------------------------------------
    # Weak Signal 2: Too many expert skills (10+)
    # ------------------------------------------------------------------
    expert_skills = [
        s for s in skills
        if _proficiency_value(s.get("proficiency", "")) >= 4
    ]
    if len(expert_skills) >= 12:
        # 12+ is extreme enough to be a strong signal
        strong_flags.append(f"too-many-experts: {len(expert_skills)}")
    elif len(expert_skills) >= 10:
        flags.append(f"too-many-experts: {len(expert_skills)}")

    # ------------------------------------------------------------------
    # Weak Signal 3: Advanced/expert proficiency on skills never used (4+)
    # ------------------------------------------------------------------
    advanced_zero = [
        s["name"]
        for s in skills
        if _proficiency_value(s.get("proficiency", "")) >= 3
        and int(s.get("duration_months") or 0) == 0
    ]
    if len(advanced_zero) >= 5:
        strong_flags.append(
            f"advanced-0month({len(advanced_zero)}): {', '.join(advanced_zero[:3])}"
        )
    elif len(advanced_zero) >= 3:
        flags.append(f"advanced-0month({len(advanced_zero)}): {', '.join(advanced_zero[:3])}")

    # ------------------------------------------------------------------
    # Decision: 1 strong flag OR 2+ weak flags = honeypot
    # ------------------------------------------------------------------
    all_flags = strong_flags + flags
    is_hp = len(strong_flags) >= 1 or len(flags) >= 2
    reason = "; ".join(all_flags) if all_flags else ""
    return is_hp, reason


def detect_honeypots(candidates: list[dict]) -> set[str]:
    """
    Return a set of candidate_ids that are identified as honeypots.
    """
    honeypot_ids: set[str] = set()
    for c in candidates:
        cid = c.get("candidate_id", "")
        is_hp, _ = _is_honeypot(c)
        if is_hp:
            honeypot_ids.add(cid)
    return honeypot_ids


def honeypot_score(candidate: dict) -> float:
    """
    Return a 0.0–1.0 suspicion score even for borderline cases.
    0.0 = definitely clean, 1.0 = definite honeypot.
    Used as a soft penalty in the main scorer.
    """
    skills: list[dict] = candidate.get("skills", [])
    career: list[dict] = candidate.get("career_history", [])
    profile: dict = candidate.get("profile", {})

    score = 0.0

    # Expert with 0 months
    zero_expert = sum(
        1 for s in skills
        if _proficiency_value(s.get("proficiency", "")) >= 4
        and int(s.get("duration_months") or 0) == 0
    )
    score += min(zero_expert * 0.2, 0.6)

    # Too many expert skills
    n_expert = sum(
        1 for s in skills
        if _proficiency_value(s.get("proficiency", "")) >= 4
    )
    if n_expert >= 10:
        score += 0.3
    elif n_expert >= 7:
        score += 0.1

    # Inflated tenure
    yoe = float(profile.get("years_of_experience") or 0)
    total_months = sum(int(r.get("duration_months") or 0) for r in career)
    if yoe > 0:
        ratio = total_months / (yoe * 12)
        if ratio > 2.5:
            score += min((ratio - 2.5) * 0.2, 0.4)

    return min(score, 1.0)
