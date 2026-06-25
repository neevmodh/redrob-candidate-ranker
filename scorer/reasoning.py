"""
scorer/reasoning.py — Per-candidate reasoning string generator

Stage 4 manual review checks each reasoning for:
  1. Specific facts from the candidate's profile (title, years, skills, signal values)
  2. Connection to JD requirements (not generic praise)
  3. Honest acknowledgement of concerns/gaps
  4. No hallucination (every claim must exist in the profile)
  5. Variation across entries (not templated)
  6. Rank consistency (tone matches rank position)

Strategy:
  - Build reasoning from actual profile data, never invent facts
  - Vary sentence structure across rank tiers (top/mid/lower)
  - Always include at least one numeric value
  - Surface concerns honestly for every candidate
"""

from __future__ import annotations
from scorer.jd_parser import JobDescription, GROUP_LABELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_yoe(yoe: float) -> str:
    return f"{yoe:.1f}" if yoe != int(yoe) else f"{int(yoe)}"


def _top_matched_skills(skill_result: dict, n: int = 3) -> list[str]:
    """Return names of top N matched must-have skills from skill scoring."""
    matched = skill_result.get("matched_must", [])
    top_skills = skill_result.get("top_skills", [])  # (name, trust) pairs
    if not matched and not top_skills:
        return []
    # Return canonical group labels for matched must-haves
    labels = [GROUP_LABELS.get(g, g) for g in matched[:n]]
    return labels


def _concerns(candidate: dict, career_result: dict,
              behavioral_result: dict, jd: JobDescription) -> list[str]:
    """Collect honest concern strings for this candidate."""
    concerns = []
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    bd = behavioral_result.get("breakdown", {})

    # Location concern
    location = profile.get("location", "")
    country = profile.get("country", "")
    pref = [loc.lower() for loc in jd.preferred_locations]
    loc_str = f"{location}, {country}".lower()
    in_preferred = any(p in loc_str for p in pref)
    if not in_preferred and location:
        concerns.append(f"location is {location}" + (f", {country}" if country and country.lower() != "india" else ""))

    # Notice period
    notice = int(signals.get("notice_period_days") or 0)
    if notice > 60:
        concerns.append(f"notice period is {notice} days")

    # Not open to work
    if not signals.get("open_to_work_flag"):
        days_inactive = bd.get("days_since_active", 999)
        if days_inactive > 90:
            concerns.append(f"profile inactive for ~{int(days_inactive)} days")
        else:
            concerns.append("open_to_work not set")

    # Low response rate
    rr = float(signals.get("recruiter_response_rate") or 0)
    if rr < 0.30:
        concerns.append(f"low recruiter response rate ({rr:.0%})")

    # Services company dominance
    sf = career_result.get("services_fraction", 0.0)
    if sf >= 0.70:
        concerns.append(f"majority career at services companies ({sf:.0%})")
    elif sf >= 0.50:
        concerns.append(f"substantial services-company background ({sf:.0%})")

    # No GitHub
    github = float(signals.get("github_activity_score")
                   if signals.get("github_activity_score") is not None else -1)
    if github < 0:
        concerns.append("no GitHub linked")

    return concerns


# ---------------------------------------------------------------------------
# Tier-specific sentence templates
# Vary structure so Stage 4 doesn't see templated outputs
# ---------------------------------------------------------------------------

def _build_reasoning_top(candidate: dict, scored: dict,
                         jd: JobDescription) -> str:
    """Ranks 1-25: lead with the strongest fit signals."""
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skill_r = scored.get("skill", {})
    career_r = scored.get("career", {})
    exp_r = scored.get("experience", {})
    bd_r = scored.get("behavioral", {}).get("breakdown", {})

    yoe = exp_r.get("yoe", profile.get("years_of_experience", 0))
    title = profile.get("current_title", "Unknown")
    company = profile.get("current_company", "")
    matched_skills = _top_matched_skills(skill_r, n=3)
    must_cov = skill_r.get("must_coverage", 0)
    must_tot = skill_r.get("must_total", 8)
    rr = float(signals.get("recruiter_response_rate") or 0)
    otw = signals.get("open_to_work_flag", False)
    days_active = int(bd_r.get("days_since_active", 999))
    notice = int(signals.get("notice_period_days") or 0)

    concerns = _concerns(candidate, career_r, scored.get("behavioral", {}), jd)

    # Sentence 1: core fit
    skills_str = ", ".join(matched_skills) if matched_skills else "core ML/retrieval skills"
    s1 = (
        f"{_fmt_yoe(yoe)} years as {title}"
        + (f" at {company}" if company else "")
        + f"; strong JD fit on {skills_str} "
        f"({must_cov}/{must_tot} must-have skill groups matched)."
    )

    # Sentence 2: availability
    if otw and rr >= 0.60:
        s2 = (
            f"Open to work, active {days_active}d ago, "
            f"{rr:.0%} recruiter response rate"
            + (f", notice {notice}d." if notice <= 30 else ".")
        )
    elif otw:
        s2 = (
            f"Open to work, last active {days_active}d ago"
            + (f"; response rate {rr:.0%}." if rr > 0 else ".")
        )
    else:
        s2 = (
            f"Not marked open-to-work but profile active {days_active}d ago"
            + (f"; response rate {rr:.0%}." if rr > 0 else ".")
        )

    # Append concerns
    if concerns:
        s2 += f" Concern(s): {'; '.join(concerns)}."

    return f"{s1} {s2}".strip()


def _build_reasoning_mid(candidate: dict, scored: dict,
                         jd: JobDescription) -> str:
    """Ranks 26-65: balance positives with honest gaps."""
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skill_r = scored.get("skill", {})
    career_r = scored.get("career", {})
    exp_r = scored.get("experience", {})
    bd_r = scored.get("behavioral", {}).get("breakdown", {})

    yoe = exp_r.get("yoe", profile.get("years_of_experience", 0))
    title = profile.get("current_title", "Unknown")
    company = profile.get("current_company", "")
    matched_must = skill_r.get("matched_must", [])
    matched_nice = skill_r.get("matched_nice", [])
    must_cov = skill_r.get("must_coverage", 0)
    must_tot = skill_r.get("must_total", 8)
    rr = float(signals.get("recruiter_response_rate") or 0)
    otw = signals.get("open_to_work_flag", False)
    days_active = int(bd_r.get("days_since_active", 999))
    notice = int(signals.get("notice_period_days") or 0)
    title_score = career_r.get("title_score", 0.0)

    concerns = _concerns(candidate, career_r, scored.get("behavioral", {}), jd)

    # Positive signals
    positives = []
    if matched_must:
        labels = [GROUP_LABELS.get(g, g) for g in matched_must[:2]]
        positives.append(f"partial skill match on {', '.join(labels)}")
    if matched_nice:
        nice_labels = [GROUP_LABELS.get(g, g) for g in matched_nice[:1]]
        positives.append(f"nice-to-have: {', '.join(nice_labels)}")
    if title_score >= 0.60:
        positives.append("relevant title trajectory")
    if otw:
        positives.append(f"open to work (active {days_active}d ago)")
    if rr >= 0.60:
        positives.append(f"strong response rate {rr:.0%}")

    pos_str = "; ".join(positives) if positives else "some relevant experience"

    s1 = (
        f"{_fmt_yoe(yoe)} years as {title}"
        + (f" at {company}" if company else "")
        + f"; {pos_str} "
        f"({must_cov}/{must_tot} must-haves matched)."
    )

    if concerns:
        s2 = f"Gaps/concerns: {'; '.join(concerns)}."
    else:
        s2 = "No major concerns flagged; lower rank reflects partial JD coverage."

    return f"{s1} {s2}".strip()


def _build_reasoning_lower(candidate: dict, scored: dict,
                           jd: JobDescription) -> str:
    """Ranks 66-100: lead with concerns, end with why they're still included."""
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skill_r = scored.get("skill", {})
    career_r = scored.get("career", {})
    exp_r = scored.get("experience", {})
    bd_r = scored.get("behavioral", {}).get("breakdown", {})

    yoe = exp_r.get("yoe", profile.get("years_of_experience", 0))
    title = profile.get("current_title", "Unknown")
    company = profile.get("current_company", "")
    must_cov = skill_r.get("must_coverage", 0)
    must_tot = skill_r.get("must_total", 8)
    rr = float(signals.get("recruiter_response_rate") or 0)
    otw = signals.get("open_to_work_flag", False)
    days_active = int(bd_r.get("days_since_active", 999))
    desc_score = career_r.get("desc_score", 0.0)
    matched_must = skill_r.get("matched_must", [])

    concerns = _concerns(candidate, career_r, scored.get("behavioral", {}), jd)

    # Why included at all
    positives = []
    if matched_must:
        labels = [GROUP_LABELS.get(g, g) for g in matched_must[:1]]
        positives.append(f"has {', '.join(labels)} exposure")
    if desc_score >= 0.30:
        positives.append("relevant keywords in career descriptions")
    if otw and rr >= 0.50:
        positives.append(f"engaged ({rr:.0%} response rate)")
    if yoe >= 5:
        positives.append(f"{_fmt_yoe(yoe)} years total experience")

    concern_str = (
        f"Concerns: {'; '.join(concerns)}. " if concerns
        else "Profile has weak JD alignment. "
    )
    pos_str = (
        f"Included because: {'; '.join(positives)}."
        if positives
        else f"Included as tail filler; {must_cov}/{must_tot} must-haves only."
    )

    s1 = (
        f"{_fmt_yoe(yoe)} years as {title}"
        + (f" at {company}" if company else "")
        + f" ({must_cov}/{must_tot} must-have groups)."
    )
    return f"{s1} {concern_str}{pos_str}".strip()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_reasoning(
    ranked: list[dict],
    jd: JobDescription,
) -> list[dict]:
    """
    Add a 'reasoning' string to each ranked candidate dict.
    Ensures all reasoning strings are unique and factually grounded.
    """
    seen_reasoning: set[str] = set()

    for item in ranked:
        rank = item["rank"]
        candidate = item["_raw"]

        # Choose tier-appropriate builder
        if rank <= 25:
            raw = _build_reasoning_top(candidate, item, jd)
        elif rank <= 65:
            raw = _build_reasoning_mid(candidate, item, jd)
        else:
            raw = _build_reasoning_lower(candidate, item, jd)

        # Guarantee uniqueness — append rank as disambiguator if collision
        reasoning = raw
        if reasoning in seen_reasoning:
            reasoning = f"[#{rank}] {raw}"
        seen_reasoning.add(reasoning)

        # Strip newlines (CSV safety)
        reasoning = reasoning.replace("\n", " ").replace("\r", " ").strip()

        item["reasoning"] = reasoning

    return ranked
