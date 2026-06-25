#!/usr/bin/env python3
"""
rank.py — Redrob Intelligent Candidate Ranking System

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Constraints:
    - CPU only, no GPU, no network during ranking
    - <=5 min wall-clock, <=16 GB RAM
    - Outputs exactly 100 rows ranked 1-100
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from scorer.honeypot import detect_honeypots
from scorer.jd_parser import get_job_description
from scorer.ranker import rank_candidates
from scorer.reasoning import generate_reasoning


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_candidates(path: str) -> list[dict]:
    """
    Stream-load candidates from a .jsonl or .json file.
    Memory-efficient: reads line by line for JSONL.
    """
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    candidates = []
    suffix = p.suffix.lower()

    if suffix == ".json":
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Accept both a list or a single object
        candidates = data if isinstance(data, list) else [data]

    elif suffix == ".jsonl":
        with open(p, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    candidates.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"[WARN] Skipping line {lineno}: {e}", file=sys.stderr)
                if lineno % 10_000 == 0:
                    print(f"  Loaded {lineno:,} candidates...", flush=True)
    else:
        print(f"[ERROR] Unsupported file type: {suffix}. Use .jsonl or .json",
              file=sys.stderr)
        sys.exit(1)

    return candidates


def validate_candidates(candidates: list[dict]) -> None:
    """Light validation — check required top-level keys exist."""
    required = {"candidate_id", "profile", "career_history",
                "education", "skills", "redrob_signals"}
    bad = 0
    for c in candidates[:100]:  # sample check on first 100
        missing = required - set(c.keys())
        if missing:
            print(f"[WARN] {c.get('candidate_id','?')} missing fields: {missing}",
                  file=sys.stderr)
            bad += 1
    if bad:
        print(f"[WARN] {bad} candidates (in first 100) had missing required fields.",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def write_submission(ranked: list[dict], out_path: str) -> None:
    """
    Write the top-100 ranked candidates to a CSV file matching the spec:
        candidate_id, rank, score, reasoning
    Scores are non-increasing with rank.
    """
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        # Enforce strictly non-increasing scores at output time.
        # Track the last formatted string value to detect 4-decimal ties.
        prev_written_float = None
        for row in ranked:
            raw_score = row["final_score"]
            # Nudge down by rank-based epsilon to differentiate similar scores
            rank_epsilon = row["rank"] * 1e-7
            score_out = max(0.0, raw_score - rank_epsilon)

            # Guarantee strictly non-increasing at 4 decimal places
            if prev_written_float is not None:
                # If formatted output would be >= previous, force it down
                while round(score_out, 4) >= round(prev_written_float, 4):
                    score_out -= 0.00005
                score_out = max(0.0, score_out)
            prev_written_float = score_out

            writer.writerow([
                row["candidate_id"],
                row["rank"],
                f"{score_out:.4f}",
                row["reasoning"],
            ])

    print(f"[OK] Submission written to: {out_path}  ({len(ranked)} rows)")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Redrob Intelligent Candidate Ranking System"
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates.jsonl (or sample_candidates.json)",
    )
    parser.add_argument(
        "--out",
        default="submission.csv",
        help="Output CSV path (default: submission.csv)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Number of top candidates to output (default: 100)",
    )
    args = parser.parse_args()

    total_start = time.perf_counter()

    # ------------------------------------------------------------------
    # Stage 1: Load candidates
    # ------------------------------------------------------------------
    print("\n[1/5] Loading candidates...")
    t0 = time.perf_counter()
    candidates = load_candidates(args.candidates)
    validate_candidates(candidates)
    t1 = time.perf_counter()
    print(f"  => {len(candidates):,} candidates loaded in {t1-t0:.2f}s")

    # ------------------------------------------------------------------
    # Stage 2: Load JD
    # ------------------------------------------------------------------
    print("\n[2/5] Parsing job description...")
    jd = get_job_description()
    print(f"  => JD parsed: {len(jd.must_have_skills)} must-have skills, "
          f"{len(jd.nice_to_have_skills)} nice-to-have skills")

    # ------------------------------------------------------------------
    # Stage 3: Detect honeypots
    # ------------------------------------------------------------------
    print("\n[3/5] Detecting honeypot candidates...")
    t0 = time.perf_counter()
    honeypot_ids = detect_honeypots(candidates)
    t1 = time.perf_counter()
    print(f"  => {len(honeypot_ids)} honeypots detected in {t1-t0:.2f}s")

    # ------------------------------------------------------------------
    # Stage 4: Score and rank
    # ------------------------------------------------------------------
    print("\n[4/5] Scoring and ranking candidates...")
    t0 = time.perf_counter()
    scored = rank_candidates(candidates, jd, honeypot_ids, top_n=args.top_n)
    t1 = time.perf_counter()
    print(f"  => Top {len(scored)} candidates ranked in {t1-t0:.2f}s")

    # ------------------------------------------------------------------
    # Stage 5: Generate reasoning
    # ------------------------------------------------------------------
    print("\n[5/5] Generating reasoning strings...")
    t0 = time.perf_counter()
    final = generate_reasoning(scored, jd)
    t1 = time.perf_counter()
    print(f"  => Reasoning generated in {t1-t0:.2f}s")

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    write_submission(final, args.out)

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[DONE] Total wall-clock time: {total_elapsed:.2f}s "
          f"({'OK' if total_elapsed < 300 else 'WARNING: over 5-min budget'})")

    # Quick sanity print of top-5
    print("\nTop 5 candidates:")
    for row in final[:5]:
        print(f"  #{row['rank']:>3}  {row['candidate_id']}  "
              f"score={row['final_score']:.4f}  {row['reasoning'][:80]}...")


if __name__ == "__main__":
    main()
