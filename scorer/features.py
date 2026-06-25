"""
scorer/features.py — Feature extraction and scoring

Three scoring components:
  1. skill_score       — JD skill overlap with endorsement+duration trust
  2. career_score      — Title relevance + product company vs services + descriptions
  3. experience_score  — Years in applied ML roles + education
"""

from __future__ import annotations
import re
from scorer.jd_parser import JobDescription, normalise_skill, SKILL_ALIASES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proficiency_value(p: str) -> float:
    return {"beginner": 0.25, "intermediate": 0.5,
            "advanced": 0.75, "expert": 1.0}.get(p.lower().strip(), 0.0)


def _text_contains(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in text (case-insensitive)."""
    t = text.lower()
    return sum(1 for kw in keywords if kw.lower() in t)


def _best_title_match(title: str, jd: JobDescription) -> float:
    """
    Score a job title against JD ideal titles.
    Returns 0.0–1.0.
    """
    t_lower = title.lower().strip()

    # Exact match against ideal titles
    for ideal in jd.ideal_titles:
        if ideal.lower() == t_lower:
            return 1.0

    # Partial keyword match
    hits = sum(1 for kw in jd.ideal_title_keywords if kw in t_lower)
    if hits >= 2:
        return 0.85
    if hits == 1:
        return 0.60

    # Negative title signals — these are keyword stuffers
    bad_titles = [
        "marketing manager", "hr manager", "accountant", "content writer",
        "graphic designer", "civil engineer", "mechanical engineer",
        "customer support", "sales executive", "operations manager",
        "project manager", "business analyst",
    ]
    if any(bt in t_lower for bt in bad_titles):
        return 0.05

    return 0.20  # unknown / generic


def _is_services_company(company: str, jd: JobDescription) -> bool:
    c_lower = company.lower().strip()
    return any(kw in c_lower for kw in jd.disqualifier_company_keywords)


# ---------------------------------------------------------------------------
# 1. SKILL SCORE
# ---------------------------------------------------------------------------

def compute_skill_score(candidate: dict, jd: JobDescription) -> dict:
    """
    Score candidate skills against JD must-haves and nice-to-haves.
    Uses a trust multiplier: endorsements * duration * proficiency.

    Returns dict with:
        score          float 0-1
        matched_must   list of matched must-have canonical groups
        matched_nice   list of matched nice-to-have canonical groups
        top_skills     list of (skill_name, trust) for top matched skills
        verified_bonus float
    """
    skills: list[dict] = candidate.get("skills", [])
    signals: dict = candidate.get("redrob_signals", {})
    assessment_scores: dict = signals.get("skill_assessment_scores", {}) or {}

    must_have_set = set(jd.must_have_skills)
    nice_have_set = set(jd.nice_to_have_skills)

    # Map canonical_group -> best trust score across all candidate skills
    group_trust: dict[str, float] = {}
    top_skills: list[tuple[str, float]] = []

    for s in skills:
        name = s.get("name", "")
        proficiency = s.get("proficiency", "beginner")
        endorsements = int(s.get("endorsements") or 0)
        duration = int(s.get("duration_months") or 0)

        # Trust score: weighted combination
        prof_val = _proficiency_value(proficiency)
        endorse_val = min(endorsements, 50) / 50.0
        dur_val = min(duration, 48) / 48.0

        # Honeypot penalty: expert with 0 months = very low trust
        if prof_val >= 1.0 and duration == 0:
            trust = 0.05
        elif prof_val >= 0.75 and duration == 0:
            trust = 0.10
        else:
            trust = (
                0.40 * endorse_val +
                0.40 * dur_val +
                0.20 * prof_val
            )

        # Assessment score bonus (verified skill)
        name_lower = name.lower()
        for assessed_skill, assessed_score in assessment_scores.items():
            if assessed_skill.lower() in name_lower or name_lower in assessed_skill.lower():
                trust = min(1.0, trust + (float(assessed_score) / 100.0) * 0.25)
                break

        canonical = normalise_skill(name)
        # Keep the best trust score per canonical group
        if canonical not in group_trust or trust > group_trust[canonical]:
            group_trust[canonical] = trust
            top_skills.append((name, trust))

    # Match against JD must-haves
    matched_must: list[str] = []
    must_trust_sum = 0.0
    for group in must_have_set:
        if group in group_trust:
            matched_must.append(group)
            must_trust_sum += group_trust[group]

    # Match against JD nice-to-haves
    matched_nice: list[str] = []
    nice_trust_sum = 0.0
    for group in nice_have_set:
        if group in group_trust:
            matched_nice.append(group)
            nice_trust_sum += group_trust[group]

    # Normalise
    must_score = must_trust_sum / len(must_have_set) if must_have_set else 0.0
    nice_score = (nice_trust_sum / len(nice_have_set)) * 0.3 if nice_have_set else 0.0

    # Verified assessment bonus (across all JD-relevant skills)
    relevant_assessments = [
        v for k, v in assessment_scores.items()
        if normalise_skill(k) in must_have_set | nice_have_set
    ]
    verified_bonus = (
        (sum(relevant_assessments) / len(relevant_assessments) / 100.0) * 0.15
        if relevant_assessments else 0.0
    )

    final_score = min(1.0, must_score * 0.7 + nice_score + verified_bonus)

    # Sort top_skills by trust descending
    top_skills_sorted = sorted(top_skills, key=lambda x: x[1], reverse=True)

    return {
        "score": final_score,
        "matched_must": matched_must,
        "matched_nice": matched_nice,
        "top_skills": top_skills_sorted[:5],
        "verified_bonus": verified_bonus,
        "must_coverage": len(matched_must),
        "must_total": len(must_have_set),
    }


# ---------------------------------------------------------------------------
# 2. CAREER TRAJECTORY SCORE
# ---------------------------------------------------------------------------

def compute_career_score(candidate: dict, jd: JobDescription) -> dict:
    """
    Score career trajectory:
      - Title relevance (weighted by recency)
      - Services-company penalty
      - Career description semantic match
      - Production-mindset evidence

    Returns dict with score and breakdown fields.
    """
    profile: dict = candidate.get("profile", {})
    career: list[dict] = candidate.get("career_history", [])

    current_title = profile.get("current_title", "")
    current_company = profile.get("current_company", "")

    # ---- Title scoring -----------------------------------------------
    # Current role gets highest weight
    current_title_score = _best_title_match(current_title, jd)

    # Past roles: weighted by recency (most recent = higher weight)
    past_title_scores: list[float] = []
    for role in career:
        if not role.get("is_current", False):
            past_title_scores.append(_best_title_match(role.get("title", ""), jd))

    if past_title_scores:
        # Weight past roles: first (most recent) gets 0.3, rest average 0.2
        past_weighted = past_title_scores[0] * 0.5 + (
            sum(past_title_scores[1:]) / max(len(past_title_scores[1:]), 1)
        ) * 0.5 if len(past_title_scores) > 1 else past_title_scores[0]
    else:
        past_weighted = 0.0

    title_score = current_title_score * 0.6 + past_weighted * 0.4

    # ---- Services company penalty ------------------------------------
    if not career:
        services_penalty = 1.0
    else:
        total_months = sum(int(r.get("duration_months") or 0) for r in career)
        services_months = sum(
            int(r.get("duration_months") or 0)
            for r in career
            if _is_services_company(r.get("company", ""), jd)
        )
        services_fraction = services_months / max(total_months, 1)

        if services_fraction >= 0.90:
            services_penalty = 0.25  # Almost entirely services company career
        elif services_fraction >= 0.70:
            services_penalty = 0.45
        elif services_fraction >= 0.50:
            services_penalty = 0.70
        elif services_fraction >= 0.25:
            services_penalty = 0.85  # Some services, but not majority
        else:
            services_penalty = 1.0  # Mostly product companies

    # ---- Career description keyword matching -------------------------
    all_descriptions = " ".join(
        r.get("description", "") for r in career
    ) + " " + profile.get("summary", "") + " " + profile.get("headline", "")

    # Weight descriptions by recency
    desc_keyword_hits = 0.0
    total_desc_weight = 0.0
    for i, role in enumerate(career):
        desc = role.get("description", "") + " " + role.get("title", "")
        recency_weight = 1.0 / (i + 1)  # 1.0, 0.5, 0.33, 0.25...
        hits = _text_contains(desc, jd.career_keywords)
        desc_keyword_hits += hits * recency_weight
        total_desc_weight += recency_weight

    # Normalise: 10+ keyword hits in descriptions = full score
    desc_score = min(1.0, desc_keyword_hits / 10.0)

    # ---- Production evidence bonus -----------------------------------
    production_hits = _text_contains(all_descriptions, jd.production_keywords)
    production_bonus = min(0.15, production_hits * 0.025)

    # ---- NLP/IR specific title boost ---------------------------------
    # The JD explicitly values people who understood retrieval BEFORE it was
    # fashionable — boost candidates with pre-LLM-era IR titles
    classic_ir_titles = [
        "search engineer", "information retrieval", "recommendation",
        "ranking engineer", "relevance engineer",
    ]
    classic_ir_boost = 0.0
    headline = profile.get("headline", "").lower()
    summary = profile.get("summary", "").lower()
    if any(t in headline or t in summary for t in classic_ir_titles):
        classic_ir_boost = 0.08

    # ---- Open-source / external validation --------------------------
    github_score = float(
        candidate.get("redrob_signals", {}).get("github_activity_score") or -1
    )
    opensource_bonus = 0.0
    if github_score > 0:
        opensource_bonus = min(0.05, github_score / 100.0 * 0.10)

    # ---- Combine -----------------------------------------------------
    base = (
        title_score * 0.40 +
        desc_score * 0.40 +
        production_bonus +
        classic_ir_boost +
        opensource_bonus
    )
    final_score = min(1.0, base) * services_penalty

    return {
        "score": final_score,
        "title_score": title_score,
        "current_title_score": current_title_score,
        "desc_score": desc_score,
        "services_penalty": services_penalty,
        "production_bonus": production_bonus,
        "services_fraction": services_months / max(total_months, 1) if career else 0.0,
    }


# ---------------------------------------------------------------------------
# 3. EXPERIENCE SCORE
# ---------------------------------------------------------------------------

def compute_experience_score(candidate: dict, jd: JobDescription) -> dict:
    """
    Score based on years of experience and education.
    """
    profile: dict = candidate.get("profile", {})
    career: list[dict] = candidate.get("career_history", [])
    education: list[dict] = candidate.get("education", [])

    yoe = float(profile.get("years_of_experience") or 0)

    # ---- Years of experience fit ------------------------------------
    # JD wants 5-9 years; ideal is 6-8
    if 6 <= yoe <= 8:
        yoe_score = 1.0
    elif 5 <= yoe <= 9:
        yoe_score = 0.90
    elif 4 <= yoe < 5:
        yoe_score = 0.75
    elif 9 < yoe <= 12:
        yoe_score = 0.80  # Overqualified but still valuable
    elif yoe > 12:
        yoe_score = 0.65  # Risk of being overqualified / title-chaser
    elif 3 <= yoe < 4:
        yoe_score = 0.55
    else:
        yoe_score = 0.30

    # ---- Applied ML years -------------------------------------------
    # Count months spent in ML/AI/Search roles specifically
    ml_months = 0
    total_months = 0
    ml_role_keywords = [
        "machine learning", "ml", "ai", "nlp", "data scientist",
        "search", "recommendation", "ranking", "retrieval",
        "applied scientist", "research scientist",
    ]
    for role in career:
        dur = int(role.get("duration_months") or 0)
        total_months += dur
        title_lower = role.get("title", "").lower()
        desc_lower = role.get("description", "").lower()
        if any(kw in title_lower or kw in desc_lower for kw in ml_role_keywords):
            ml_months += dur

    ml_fraction = ml_months / max(total_months, 1)
    ml_yoe_bonus = min(0.20, ml_fraction * 0.25)

    # ---- Education score --------------------------------------------
    edu_tier_map = {
        "tier_1": 1.0, "tier_2": 0.85, "tier_3": 0.65,
        "tier_4": 0.45, "unknown": 0.35,
    }
    relevant_fields = [
        "computer science", "machine learning", "artificial intelligence",
        "mathematics", "statistics", "information technology",
        "data science", "electrical engineering", "electronics",
        "software engineering",
    ]

    best_edu_score = 0.0
    for edu in education:
        tier = edu.get("tier", "unknown").lower()
        tier_score = edu_tier_map.get(tier, 0.35)
        field = edu.get("field_of_study", "").lower()
        field_bonus = 0.10 if any(f in field for f in relevant_fields) else 0.0
        edu_score = min(1.0, tier_score + field_bonus)
        if edu_score > best_edu_score:
            best_edu_score = edu_score

    if not education:
        best_edu_score = 0.30  # no info = neutral-low

    final_score = min(1.0,
        yoe_score * 0.60 +
        ml_yoe_bonus +
        best_edu_score * 0.20
    )

    return {
        "score": final_score,
        "yoe": yoe,
        "yoe_score": yoe_score,
        "ml_fraction": ml_fraction,
        "edu_score": best_edu_score,
    }
