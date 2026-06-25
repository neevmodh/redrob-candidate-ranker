"""
scorer/ranker.py — Combined score assembly and top-N ranking

Scoring weights (tuned to maximise NDCG@10 which is 50% of eval score):
    skill_score       35%  — JD skill overlap with trust multiplier
    career_score      30%  — Title + company type + description match
    experience_score  20%  — YoE fit + applied-ML years fraction
    education_score    5%  — Degree tier + relevant field (already in experience)

Final score = base_score * behavioral_multiplier  (clamped to [0, 1])

Honeypots are forced to bottom ranks with score < 0.01.
"""

from __future__ import annotations

import math
from scorer.features import (
    compute_skill_score,
    compute_career_score,
    compute_experience_score,
)
from scorer.signals import compute_behavioral_score
from scorer.honeypot import honeypot_score
from scorer.jd_parser import JobDescription


# ---------------------------------------------------------------------------
# Component weights
# ---------------------------------------------------------------------------
W_SKILL    = 0.35
W_CAREER   = 0.30
W_EXPERIENCE = 0.20
W_EDUCATION  = 0.05   # folded into experience_score already
W_SIGNALS  = 0.10     # baseline weight for behavioral in base (multiplier adds more)


def _score_single(candidate: dict, jd: JobDescription,
                  honeypot_ids: set[str]) -> dict:
    """
    Score one candidate and return a flat result dict.
    All component scores and breakdown fields are preserved for reasoning.
    """
    cid = candidate.get("candidate_id", "")

    # ---- Honeypot fast-path ----------------------------------------
    if cid in honeypot_ids:
        return {
            "candidate_id": cid,
            "final_score": 0.005,
            "is_honeypot": True,
            "skill": {}, "career": {}, "experience": {}, "behavioral": {},
            "_raw": candidate,
        }

    # ---- Soft honeypot penalty -------------------------------------
    hp_suspicion = honeypot_score(candidate)
    hp_penalty = 1.0 - hp_suspicion * 0.50  # max 50% reduction for borderline

    # ---- Component scores ------------------------------------------
    skill_result      = compute_skill_score(candidate, jd)
    career_result     = compute_career_score(candidate, jd)
    experience_result = compute_experience_score(candidate, jd)
    behavioral_result = compute_behavioral_score(candidate)

    s_skill  = skill_result["score"]
    s_career = career_result["score"]
    s_exp    = experience_result["score"]
    s_beh    = behavioral_result["multiplier"]  # already [0.5, 1.2]

    # ---- Base score (weighted sum) ---------------------------------
    base = (
        W_SKILL      * s_skill +
        W_CAREER     * s_career +
        W_EXPERIENCE * s_exp
    )

    # ---- Apply behavioral multiplier --------------------------------
    # Multiplier range [0.5, 1.2] → gives availability up to 20% boost
    # and down to 50% penalty for unavailable candidates
    final = base * s_beh * hp_penalty

    # Clamp to [0, 1]
    final = max(0.0, min(1.0, final))

    return {
        "candidate_id": cid,
        "final_score": final,
        "is_honeypot": False,
        "skill": skill_result,
        "career": career_result,
        "experience": experience_result,
        "behavioral": behavioral_result,
        "hp_suspicion": hp_suspicion,
        "_raw": candidate,
    }


def rank_candidates(
    candidates: list[dict],
    jd: JobDescription,
    honeypot_ids: set[str],
    top_n: int = 100,
) -> list[dict]:
    """
    Score all candidates, sort by final_score descending, return top_n.

    Tie-breaking: same score → sort by candidate_id ascending (per spec).
    """
    scored: list[dict] = []

    for i, c in enumerate(candidates):
        result = _score_single(c, jd, honeypot_ids)
        scored.append(result)

        # Progress feedback every 20k
        if (i + 1) % 20_000 == 0:
            print(f"  Scored {i+1:,} / {len(candidates):,}...", flush=True)

    # Sort: score descending, then candidate_id ascending for ties
    scored.sort(key=lambda x: (-x["final_score"], x["candidate_id"]))

    # Assign ranks 1-N
    top = scored[:top_n]
    for rank_idx, item in enumerate(top, start=1):
        item["rank"] = rank_idx

    # Ensure scores are strictly non-increasing (spec requirement)
    # If ties exist, scores are already equal so non-increasing holds
    # Final safety clamp
    prev_score = 1.0
    for item in top:
        if item["final_score"] > prev_score:
            item["final_score"] = prev_score
        prev_score = item["final_score"]

    return top
