# Redrob Intelligent Candidate Ranking System

**Team: LeConHinton**
**Hackathon: Redrob AI — Track 01: Intelligent Candidate Discovery**
**GitHub:** https://github.com/neevmodh/redrob-candidate-ranker
**Live Demo:** https://redrobai-candidate-ranker.streamlit.app/

---

## Quick Start

```bash
pip install -r requirements.txt
python rank.py --candidates ./candidates.jsonl --out ./leconhinton.csv
python validate_submission.py leconhinton.csv
```

**Runtime:** ~25 seconds on CPU. Well within the 5-minute budget.
**Memory:** ~1.2 GB peak. Well within 16 GB limit.
**Network:** Zero — fully offline, no API calls.

---

## Problem Statement

Given 100,000 candidate profiles with structured attributes, career history, skills,
and behavioral signals from the Redrob platform, rank the top 100 candidates for a
**Senior AI Engineer (Founding Team)** role at Redrob AI (Series A, Pune/Noida).

The core challenge: go beyond keyword matching. The JD explicitly warns that candidates
whose skills section contains AI keywords but whose career is irrelevant (e.g., "Marketing
Manager" with "FAISS" listed) should rank low. The right signals are career trajectory,
production deployment evidence, and behavioral availability — not keyword overlap.

---

## Live Demo (Sandbox)

**URL:** https://redrobai-candidate-ranker.streamlit.app/

Upload `sample_candidates.json` (included in this repo) to test the ranker live:
- Drag and drop the file into the uploader
- Click **Run Ranker**
- View ranked results with per-candidate score breakdowns
- Download the submission-ready CSV

---

## System Architecture

```
candidates.jsonl (100K)
        │
        ▼
┌─────────────────────┐
│  Stage 1: Load      │  Stream JSONL line-by-line, ~4.5s
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Stage 2: JD Parse  │  Hardcoded JD → structured JobDescription object
└──────────┬──────────┘  (must-haves, nice-to-haves, disqualifiers)
           │
           ▼
┌─────────────────────┐
│  Stage 3: Honeypots │  Flag impossible profiles (72 detected in dataset)
└──────────┬──────────┘
           │
           ▼
┌────────────────────────────────────────────────────┐
│  Stage 4: Score each candidate (~19s for 100K)     │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ Skill Score  │  │Career Score  │               │
│  │   (35%)      │  │   (30%)      │               │
│  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                        │
│  ┌──────┴───────┐  ┌──────┴───────┐               │
│  │  Exp Score   │  │  Behavioral  │               │
│  │   (20%)      │  │  Multiplier  │               │
│  └──────┬───────┘  └──────┬───────┘               │
│         └────────┬─────────┘                       │
│               base_score × behavioral_mult         │
└───────────────────┬────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │  Stage 5: Sort,   │  Top-100, ranks 1-100
        │  rank, reason     │  Unique per-candidate reasoning strings
        └───────────────────┘
                    │
                    ▼
             leconhinton.csv
```

---

## Scoring Methodology

### Component 1 — Skill Match Score (35%)

Scores candidate skills against 8 JD must-have skill groups and 5 nice-to-have groups.

**Anti-keyword-stuffing trust multiplier:**

Each skill is scored on three dimensions before matching:
- **Endorsements (40%)** — `min(endorsements, 50) / 50`
- **Duration used (40%)** — `min(duration_months, 48) / 48`
- **Proficiency (20%)** — beginner=0.25, intermediate=0.5, advanced=0.75, expert=1.0

Key penalty: `proficiency=expert` + `duration_months=0` → trust score drops to **0.05**.
This directly counters keyword stuffers who list "expert" skills they never used.

Platform-verified `skill_assessment_scores` add up to +0.25 bonus to that skill's trust.

**JD must-have skill groups matched:**
`embeddings`, `vector_db`, `ranking`, `eval_framework`, `python`, `nlp`, `ml_core`, `search`

**JD nice-to-have groups:**
`llm_finetuning`, `learning_to_rank`, `recsys`, `mlops`, `data_eng`

---

### Component 2 — Career Trajectory Score (30%)

The most important signal for detecting keyword stuffers and mismatched candidates.

**Title scoring (40% of career score):**
- Matched against 16 ideal titles: exact=1.0, keyword match=0.85, partial=0.60
- Bad titles (Marketing Manager, HR Manager, Accountant, etc.) = 0.05
- Weighted by recency: current title 60%, past titles 40%

**Services company penalty:**
The JD explicitly disqualifies candidates whose entire career is at body-shop companies
(TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, HCL, etc.):

| Services career fraction | Multiplier |
|--------------------------|------------|
| > 90% | 0.25× |
| 70–90% | 0.45× |
| 50–70% | 0.70× |
| < 25% | 1.00× (no penalty) |

**Career description matching (40% of career score):**
Each role description is searched for 35 JD-relevant keywords (embedding, retrieval,
ranking, faiss, pinecone, recommendation, etc.), weighted by recency. A "Marketing Manager"
who never mentions these terms scores near zero even with AI skills listed.

**Production evidence bonus:**
Descriptions containing "production", "deployed", "A/B test", "serving", "at scale",
"million users" receive a +0.15 bonus — rewarding the "shipper" mindset the JD asks for.

---

### Component 3 — Experience Score (20%)

- **Years of experience fit:** JD targets 5–9 years. Ideal 6–8 scores 1.0. Outside band penalised smoothly.
- **Applied ML fraction:** Counts months in ML/AI/Search/NLP roles vs total career. High fraction boosts score.
- **Education:** Degree tier (tier_1=1.0 → tier_4=0.45) + relevant field bonus (+0.10 for CS/ML/AI/Statistics).

---

### Behavioral Signal Multiplier

The 23 Redrob platform signals are converted to an availability multiplier in **[0.50, 1.20]**:

| Signal | Weight | Notes |
|--------|--------|-------|
| `open_to_work_flag` | High | +0.20 bonus if true |
| `last_active_date` | High | <7d=1.0, <30d=0.95, >180d=0.15 |
| `recruiter_response_rate` | Medium | Direct 0–1 pass-through |
| `avg_response_time_hours` | Medium | <24h=1.0, >168h=0.30 |
| `interview_completion_rate` | Medium | Direct pass-through |
| `notice_period_days` | Medium | ≤30d=1.0, >90d=0.55, >120d=0.40 |
| `github_activity_score` | Low | -1 (no GitHub)=0.30, 80+=1.0 |
| `offer_acceptance_rate` | Low | -1 (no history)=neutral |
| `profile_completeness_score` | Low | Normalised 0–1 |
| Verified email/phone/LinkedIn | Low | +0.05 each |

**Final formula:**
```
base_score  = 0.35 × skill_score + 0.30 × career_score + 0.20 × experience_score
final_score = base_score × behavioral_multiplier   (clamped to [0, 1])
```

---

## Honeypot Detection

The dataset contains ~80 honeypots with subtly impossible profiles. Our detector uses a
**strong/weak signal** framework:

**Strong signals (1 alone = honeypot):**
- Impossible tenure at young companies — Sarvam AI (est. April 2023, max 38 months plausible), Krutrim (est. Dec 2023, max 30 months plausible)
- 3+ expert skills with `duration_months = 0`
- 12+ expert skills total
- 5+ advanced/expert skills with `duration_months = 0`

**Weak signals (2 needed = honeypot):**
- 1–2 expert skills with `duration_months = 0`
- 10–11 expert skills total
- 3–4 advanced/expert skills with `duration_months = 0`
- Inflated tenure: total career months > 250% of `years_of_experience × 12`

**Result: 72 honeypots identified, 0 in top-100 (well below 10% disqualification threshold).**

---

## Design Decisions

**Why not pure keyword/embedding similarity?**
The JD explicitly calls this out as the trap: "find candidates whose skills section contains
the most AI keywords — that's a trap we've built into the dataset." A "Marketing Manager"
with "FAISS" and "Pinecone" listed as beginner skills should rank far below a genuine Search
Engineer. The trust multiplier (endorsements × duration × proficiency) handles this.

**Why the services-company penalty?**
The JD says: "People who have only worked at consulting firms (TCS, Infosys, Wipro, Accenture,
Cognizant, Capgemini) in their entire career — we've had bad fit experiences." This is a hard
signal that must be encoded.

**Why behavioral as a multiplier rather than additive?**
A perfect-on-paper candidate who hasn't logged in for 9 months and has a 5% response rate is
literally not hireable. Multiplying rather than adding ensures extreme unavailability kills the
final score even for high-quality profiles.

**Why NDCG@10 tuning?**
It carries 50% of the evaluation weight. Getting the top-10 right matters more than everything
else combined. The skill trust score and career trajectory score are calibrated to be harsh
discriminators at the top.

**No external models, no API calls:**
All scoring is deterministic feature engineering. No model downloads, no FAISS index, no
sentence-transformers. Entire pipeline runs in ~25 seconds on a laptop CPU.

---

## Repository Structure

```
.
├── rank.py                        # Main entrypoint — CLI, pipeline orchestration
├── app.py                         # Streamlit sandbox demo
├── requirements.txt               # Pinned dependencies
├── validate_submission.py         # Official format validator (challenge-provided)
├── leconhinton.csv                # Submission file (top-100 ranked candidates)
├── submission_metadata.yaml       # Team metadata for portal submission
├── candidate_schema.json          # JSON schema for candidate profiles (challenge-provided)
├── sample_candidates.json         # 50-candidate sample for testing
└── scorer/
    ├── __init__.py
    ├── jd_parser.py               # JD → structured JobDescription + 60-entry skill alias map
    ├── honeypot.py                # Impossible profile detection (strong/weak signal framework)
    ├── features.py                # Skill score + career trajectory + experience score
    ├── signals.py                 # 23 Redrob signals → availability multiplier [0.50, 1.20]
    ├── ranker.py                  # Score assembly, sorting, rank assignment
    └── reasoning.py               # Per-candidate reasoning string generation
```

---

## Reproduce Submission

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the ranker
python rank.py --candidates ./candidates.jsonl --out ./leconhinton.csv

# 3. Validate output format
python validate_submission.py leconhinton.csv
# Expected: "Submission is valid."
```

**Expected output:**
```
[1/5] Loading candidates...
  => 100,000 candidates loaded in ~4.5s
[2/5] Parsing job description...
  => JD parsed: 8 must-have skills, 5 nice-to-have skills
[3/5] Detecting honeypot candidates...
  => 72 honeypots detected in ~1.0s
[4/5] Scoring and ranking candidates...
  => Top 100 candidates ranked in ~19s
[5/5] Generating reasoning strings...
  => Reasoning generated in ~0.0s
[OK] Submission written to: leconhinton.csv  (100 rows)
[DONE] Total wall-clock time: ~25s (OK)
```

---

## Results — Top 10 Shortlist

| Rank | Candidate | Score | Title | Company |
|------|-----------|-------|-------|---------|
| 1 | CAND_0079387 | 0.7828 | AI Engineer | Microsoft |
| 2 | CAND_0018499 | 0.7699 | Senior Machine Learning Engineer | Zomato |
| 3 | CAND_0064326 | 0.7588 | Search Engineer | Sarvam AI |
| 4 | CAND_0046064 | 0.7539 | Senior NLP Engineer | Salesforce |
| 5 | CAND_0036184 | 0.7387 | Recommendation Systems Engineer | CRED |
| 6 | CAND_0071974 | 0.7325 | Senior AI Engineer | Netflix |
| 7 | CAND_0027691 | 0.7314 | NLP Engineer | Haptik |
| 8 | CAND_0046525 | 0.7255 | Senior Machine Learning Engineer | Genpact AI |
| 9 | CAND_0077337 | 0.7202 | Staff Machine Learning Engineer | Paytm |
| 10 | CAND_0055905 | 0.7200 | Senior Machine Learning Engineer | Flipkart |

All top-10 are ML/AI engineers at product companies with direct experience in
search, retrieval, ranking, or recommendation systems.

---

## Compute Environment

- **Platform:** MacBook Pro (Apple Silicon M-series), macOS
- **Python:** 3.14.3
- **CPU cores:** 8 | **RAM:** 16 GB | **GPU:** None
- **Network during ranking:** None (fully offline)
- **Wall-clock time:** ~25 seconds for 100K candidates
- **Peak memory:** ~1.2 GB

---

## AI Tools Declaration

- **Kiro (Claude):** Used for architecture discussion, code review, and planning
- No candidate data was fed to any LLM
- All scoring logic is hand-engineered based on JD analysis
- The system is fully deterministic feature engineering

---

## Team

**LeConHinton**
GitHub: https://github.com/neevmodh/redrob-candidate-ranker
Demo: https://redrobai-candidate-ranker.streamlit.app/
