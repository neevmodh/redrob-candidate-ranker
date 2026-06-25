<div align="center">

# 🎯 Redrob Intelligent Candidate Ranking System

**Team LeConHinton — Redrob AI Hackathon 2025 — Track 01: Intelligent Candidate Discovery**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Live%20Demo-Streamlit-red?logo=streamlit)](https://redrobai-candidate-ranker.streamlit.app/)
[![GitHub](https://img.shields.io/badge/GitHub-neevmodh-black?logo=github)](https://github.com/neevmodh/redrob-candidate-ranker)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Validation](https://img.shields.io/badge/Submission-Valid-brightgreen)](#reproduce-submission)

> Ranking 100,000 candidates against a Senior AI Engineer JD in **~25 seconds** on CPU.
> Zero API calls. Zero model downloads. Fully deterministic. Honeypot-aware.

[Live Demo](https://redrobai-candidate-ranker.streamlit.app/) •
[Quick Start](#quick-start) •
[Architecture](#system-architecture) •
[Methodology](#scoring-methodology) •
[Results](#results--top-10-shortlist)

</div>

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Quick Start](#quick-start)
- [Live Demo](#live-demo--sandbox)
- [System Architecture](#system-architecture)
- [Scoring Methodology](#scoring-methodology)
  - [Skill Match Score (35%)](#component-1--skill-match-score-35)
  - [Career Trajectory Score (30%)](#component-2--career-trajectory-score-30)
  - [Experience Score (20%)](#component-3--experience-score-20)
  - [Behavioral Multiplier](#behavioral-signal-multiplier)
- [Honeypot Detection](#honeypot-detection)
- [Design Decisions](#design-decisions)
- [Repository Structure](#repository-structure)
- [Reproduce Submission](#reproduce-submission)
- [Results — Top 10](#results--top-10-shortlist)
- [Compute Environment](#compute-environment)
- [AI Tools Declaration](#ai-tools-declaration)
- [Team](#team)

---

## Problem Statement

Given **100,000 candidate profiles** with structured attributes, career history, skills,
education, and 23 behavioral signals from the Redrob platform — rank the top 100 candidates
for a **Senior AI Engineer (Founding Team)** role at Redrob AI (Series A, Pune/Noida).

### The Core Challenge

The JD explicitly warns against the obvious approach:

> *"The right answer is NOT to find candidates whose skills section contains the most AI
> keywords. That's a trap we've built into the dataset. A candidate who has all the AI
> keywords listed as skills but whose title is 'Marketing Manager' is not a fit."*

Our system must reason about:
- **Career trajectory** — what did they actually build vs what they claim?
- **Production evidence** — did they ship to real users, or just experiment?
- **Behavioral availability** — will they actually respond to outreach?
- **Honeypots** — ~80 impossible profiles designed to fool keyword matchers

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- ~1.5 GB free RAM
- No GPU required
- No internet required during ranking

### Installation

```bash
# Clone the repository
git clone https://github.com/neevmodh/redrob-candidate-ranker.git
cd redrob-candidate-ranker

# Install dependencies (only numpy, dateutil, streamlit, pandas)
pip install -r requirements.txt
```

### Run the Ranker

```bash
# Full 100K candidate ranking (~25 seconds)
python rank.py --candidates ./candidates.jsonl --out ./leconhinton.csv

# Quick test on sample data (~0.02 seconds)
python rank.py --candidates ./sample_candidates.json --out ./test_output.csv

# Validate output format
python validate_submission.py leconhinton.csv
```

### Run the Streamlit Demo Locally

```bash
streamlit run app.py
# Opens at http://localhost:8501
# Upload sample_candidates.json to test
```

---

## Live Demo — Sandbox

**URL:** [https://redrobai-candidate-ranker.streamlit.app/](https://redrobai-candidate-ranker.streamlit.app/)

The sandbox lets judges verify the system end-to-end without running code locally:

1. Upload `sample_candidates.json` (included in this repo — 50 candidates)
2. Set desired Top-N (default 50)
3. Click **Run Ranker**
4. Inspect ranked table with color-coded tiers, score breakdowns, per-candidate reasoning
5. Download a submission-ready CSV

> The sandbox processes ≤100 candidates in under 1 second on Streamlit's free CPU tier.

---

## System Architecture

```
candidates.jsonl  (100,000 candidates, ~487 MB)
        │
        ▼
┌──────────────────────────────────────────┐
│  Stage 1: Stream Loader                  │
│  • Line-by-line JSONL parsing            │
│  • Supports .json and .jsonl formats     │
│  • ~4.5s for 100K candidates             │
└──────────────────────┬───────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────┐
│  Stage 2: JD Parser  (jd_parser.py)      │
│  • Hardcoded JD → JobDescription object  │
│  • 8 must-have skill groups              │
│  • 5 nice-to-have skill groups           │
│  • 60-entry skill alias/synonym map      │
│  • 35 career description keywords        │
│  • 16 ideal job title patterns           │
│  • 14 disqualifier company keywords      │
└──────────────────────┬───────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────┐
│  Stage 3: Honeypot Detector (honeypot.py)│
│  • Strong signals (1 = flag):            │
│    - Impossible tenure at young cos.     │
│    - 3+ expert skills, 0 months used     │
│    - 12+ expert skills total             │
│    - 5+ advanced skills, 0 months used   │
│    - Total months > 2.5× YoE × 12       │
│  • Weak signals (2 = flag):              │
│    - 1-2 expert skills, 0 months used    │
│    - 10-11 expert skills                 │
│    - 3-4 advanced skills, 0 months used  │
│  Result: 72 honeypots flagged (~80 spec) │
└──────────────────────┬───────────────────┘
                       │
              ┌────────┴────────┐
              │  For each of    │
              │  100K candidates│
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Skill Score  │ │Career Score  │ │  Experience  │
│ features.py  │ │ features.py  │ │    Score     │
│              │ │              │ │ features.py  │
│ • Trust mult │ │ • Title match│ │              │
│   endorse ×  │ │ • Services   │ │ • YoE fit    │
│   duration × │ │   company    │ │ • ML months  │
│   proficiency│ │   penalty    │ │   fraction   │
│ • Must-haves │ │ • Desc keyw. │ │ • Education  │
│ • Nice-haves │ │ • Prod evid. │ │   tier       │
│ • Assessment │ │ • IR boost   │ │              │
│   bonus      │ │ • OSS bonus  │ │              │
│              │ │              │ │              │
│   35% weight │ │   30% weight │ │   20% weight │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       └────────────────┼────────────────┘
                        │ base_score
                        ▼
              ┌──────────────────────┐
              │ Behavioral Multiplier│
              │     signals.py       │
              │                      │
              │ • open_to_work_flag  │
              │ • last_active_date   │
              │ • recruiter_resp_rate│
              │ • response_time_hrs  │
              │ • interview_rate     │
              │ • notice_period      │
              │ • github_activity    │
              │ • offer_accept_rate  │
              │ • profile_completeness│
              │ • saved_by_recruiters│
              │                      │
              │ Range: [0.50, 1.20]  │
              └──────────┬───────────┘
                         │ final = base × multiplier
                         ▼
              ┌──────────────────────┐
              │  Sort + Top-100      │
              │     ranker.py        │
              │ • Score desc order   │
              │ • Tie-break: cand_id │
              │   ascending (spec)   │
              │ • Ranks 1-100        │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Reasoning Generator │
              │    reasoning.py      │
              │ • Tier-aware (top /  │
              │   mid / lower)       │
              │ • 100 unique strings │
              │ • Specific facts only│
              │ • Honest concerns    │
              └──────────┬───────────┘
                         │
                         ▼
                  leconhinton.csv
```

---

## Scoring Methodology

### Final Formula

```
base_score  = 0.35 × skill_score
            + 0.30 × career_score
            + 0.20 × experience_score

final_score = base_score × behavioral_multiplier
            (clamped to [0.0, 1.0])
```

Weights are tuned toward **NDCG@10** (50% of evaluation) — getting the top-10 right
matters more than any other metric.

---

### Component 1 — Skill Match Score (35%)

**File:** `scorer/features.py` → `compute_skill_score()`

Scores candidate skills against 8 JD must-have groups and 5 nice-to-have groups.
Skills are normalised through a 60-entry alias map (`scorer/jd_parser.py`) before matching.

**JD Must-Have Skill Groups:**

| Group Key | Covers |
|-----------|--------|
| `embeddings` | sentence-transformers, BGE, E5, OpenAI embeddings, dense retrieval, bi-encoder |
| `vector_db` | FAISS, Pinecone, Milvus, Qdrant, Weaviate, OpenSearch, Elasticsearch, Chroma |
| `ranking` | BM25, TF-IDF, hybrid search, information retrieval, ranker |
| `eval_framework` | NDCG, MRR, MAP, A/B testing, recall@k, precision@k |
| `python` | Python |
| `nlp` | NLP, transformers, BERT, GPT, LLMs, RAG, text classification |
| `ml_core` | PyTorch, TensorFlow, scikit-learn, deep learning, statistical modeling |
| `search` | search engineering, vector search, Solr, Lucene |

**JD Nice-to-Have Groups:** `llm_finetuning` (LoRA/QLoRA/PEFT), `learning_to_rank`
(XGBoost LTR), `recsys` (recommendation systems), `mlops` (MLflow/Kubeflow),
`data_eng` (Spark/Kafka/Airflow)

#### Trust Multiplier — The Anti-Keyword-Stuffer Mechanism

Each skill gets a **trust score** before matching. This is the core defense against
candidates who list skills they never actually used:

```python
# Standard trust calculation
trust = 0.40 × (min(endorsements, 50) / 50)   # peer-validated
      + 0.40 × (min(duration_months, 48) / 48) # actually used it
      + 0.20 × proficiency_value               # self-reported level

# Honeypot penalty — expert claim with 0 months = fabricated
if proficiency == "expert" and duration_months == 0:
    trust = 0.05   # almost zero — near-disqualifying
elif proficiency == "advanced" and duration_months == 0:
    trust = 0.10
```

**Proficiency mapping:** `beginner=0.25`, `intermediate=0.50`, `advanced=0.75`, `expert=1.0`

Platform-verified `skill_assessment_scores` add up to **+0.25** bonus to that skill's trust.

**Score formula:**
```
must_score    = Σ trust[matched_must_haves] / len(must_have_groups)
nice_score    = Σ trust[matched_nice_haves] / len(nice_have_groups) × 0.30
verified_bonus = mean(assessment_scores for matched skills) / 100 × 0.15

skill_score = min(1.0,  must_score × 0.70 + nice_score + verified_bonus)
```

---

### Component 2 — Career Trajectory Score (30%)

**File:** `scorer/features.py` → `compute_career_score()`

The most critical discriminator. A "Marketing Manager" with a perfect skill list
should score near zero; a "Search Engineer" with only 3 relevant skills should
score highly.

#### Sub-component: Title Scoring (40% of career score)

Titles are matched against 16 ideal patterns with recency weighting:

```
Current title:  60% weight
Past titles:    40% weight (most recent past = higher sub-weight)
```

**Title score mapping:**
- Exact match to ideal title (e.g., "Senior NLP Engineer") → **1.0**
- 2+ keyword matches (e.g., "Lead ML Researcher") → **0.85**
- 1 keyword match (e.g., "AI Specialist") → **0.60**
- Explicit bad title (Marketing Manager, HR Manager, Accountant, etc.) → **0.05**
- Unknown/generic → **0.20**

#### Sub-component: Services Company Penalty

The JD explicitly disqualifies candidates whose career is primarily at body-shop firms.
Applied as a **multiplier on the entire career score**:

| Services Career Fraction | Penalty Multiplier |
|--------------------------|-------------------|
| ≥ 90% at services firms | **0.25×** |
| 70% – 90% | **0.45×** |
| 50% – 70% | **0.70×** |
| 25% – 50% | **0.85×** |
| < 25% | **1.00×** (no penalty) |

Disqualified companies: TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, HCL,
Tech Mahindra, Mphasis, Hexaware, Mindtree, LTIMindtree.

#### Sub-component: Career Description Matching (40% of career score)

Each role description is scanned for 35 JD-relevant keywords, weighted by recency:

```python
# Recency weighting: current role = 1.0×, previous = 0.5×, before that = 0.33×...
recency_weight = 1.0 / (role_index + 1)
desc_keyword_hits += count_keywords(description, jd.career_keywords) × recency_weight

# Normalise: 10+ hits = full score
desc_score = min(1.0, desc_keyword_hits / 10.0)
```

Keywords searched: `embedding`, `retrieval`, `ranking`, `search`, `vector`, `faiss`,
`pinecone`, `recommendation`, `nlp`, `transformer`, `bm25`, `hybrid search`, `rag`,
`reranking`, `ndcg`, `mrr`, `a/b test`, `relevance`, `inference`, `latency`, and 15 more.

#### Additional Bonuses

- **Production evidence** (+0.15 max): descriptions containing "production", "deployed",
  "shipped", "at scale", "serving", "A/B", "million users" → rewards the "shipper" mindset
- **Classic IR boost** (+0.08): headline/summary mentions "search engineer", "information
  retrieval", "recommendation" → rewards pre-LLM-era expertise the JD explicitly values
- **Open-source** (+0.05 max): GitHub activity score > 0 → rewards external validation

---

### Component 3 — Experience Score (20%)

**File:** `scorer/features.py` → `compute_experience_score()`

#### Years of Experience Fit

JD targets 5–9 years, ideal 6–8:

| YoE Range | Score |
|-----------|-------|
| 6 – 8 years | **1.00** (ideal) |
| 5 – 9 years | **0.90** |
| 4 – 5 years | **0.75** |
| 9 – 12 years | **0.80** (slight overqualification) |
| > 12 years | **0.65** (title-chaser risk) |
| 3 – 4 years | **0.55** |
| < 3 years | **0.30** |

#### Applied ML Fraction Bonus

Counts months spent in ML/AI/Search/NLP roles vs total career:

```python
ml_role_keywords = ["machine learning", "ml", "ai", "nlp", "data scientist",
                    "search", "recommendation", "ranking", "retrieval", ...]

ml_fraction = ml_months / total_career_months
ml_yoe_bonus = min(0.20, ml_fraction × 0.25)
```

#### Education Score

| Tier | Score |
|------|-------|
| tier_1 (IIT, IISc, NIT top) | **1.00** |
| tier_2 | **0.85** |
| tier_3 (Chandigarh U, LPU) | **0.65** |
| tier_4 (Local colleges) | **0.45** |
| unknown | **0.35** |

+0.10 bonus for relevant field: CS, ML, AI, Mathematics, Statistics, Data Science,
Electrical/Electronics Engineering, Software Engineering.

**Final formula:**
```
experience_score = min(1.0,
    yoe_score × 0.60 + ml_yoe_bonus + education_score × 0.20
)
```

---

### Behavioral Signal Multiplier

**File:** `scorer/signals.py` → `compute_behavioral_score()`

Converts all 23 Redrob platform signals into a single multiplier in **[0.50, 1.20]**
applied multiplicatively to the base score.

> *"A perfect-on-paper candidate who hasn't logged in for 6 months and has a 5%
> response rate is, for hiring purposes, not actually available."* — JD

#### Signal Groups and Weights

**Availability (40% of raw multiplier):**

| Signal | How scored |
|--------|-----------|
| `open_to_work_flag` | +0.20 bonus if `true` |
| `last_active_date` | ≤7d=1.0, ≤30d=0.95, ≤60d=0.85, ≤90d=0.75, ≤180d=0.55, ≤270d=0.35, >270d=0.15 |

**Responsiveness (30% of raw multiplier):**

| Signal | How scored |
|--------|-----------|
| `recruiter_response_rate` | Direct 0.0–1.0 (50% weight) |
| `avg_response_time_hours` | ≤12h=1.0, ≤24h=0.90, ≤48h=0.80, >168h=0.30 (30% weight) |
| `interview_completion_rate` | Direct 0.0–1.0 (20% weight) |

**Notice Period Fit (15% of raw multiplier):**

| Days | Score | JD note |
|------|-------|---------|
| ≤15 | 1.00 | Immediate |
| ≤30 | 0.95 | JD preferred |
| ≤45 | 0.80 | Buyout feasible |
| ≤60 | 0.70 | |
| ≤90 | 0.55 | |
| ≤120 | 0.40 | |
| >120 | 0.25 | Hard to hire |

**Profile Quality (15% of raw multiplier):**

| Signal | Weight |
|--------|--------|
| `profile_completeness_score` | 35% |
| `github_activity_score` | 25% (−1=0.30, 0=0.35, ≤20=0.55, ≤50=0.75, 80+=1.0) |
| `offer_acceptance_rate` | 20% (−1=neutral 0.60) |
| `saved_by_recruiters_30d` | min(0.10, count × 0.01) |
| `verified_email` + `verified_phone` | +0.05 each |
| `linkedin_connected` | +0.03 |

**Multiplier mapping:**
```python
raw    = 0.40 × availability + 0.30 × responsiveness
       + 0.15 × notice_fit   + 0.15 × profile_quality

multiplier = 0.50 + raw × 0.70   # maps [0,1] → [0.50, 1.20]

# Hard floor for completely unavailable candidates
if not open_to_work and days_inactive > 270:
    multiplier = min(multiplier, 0.62)

# Premium boost for highly engaged candidates
if open_to_work and response_rate >= 0.80 and days_inactive <= 30:
    multiplier = min(1.20, multiplier + 0.08)
```

---

## Honeypot Detection

**File:** `scorer/honeypot.py`

The dataset contains ~80 honeypot candidates with subtly impossible profiles. The challenge
spec states: submissions with >10% honeypots in top-100 are **disqualified**.

Our detector uses a **strong/weak signal framework** — one strong signal alone is enough
to flag a honeypot; weak signals require two or more.

### Strong Signals (1 alone = honeypot)

| Signal | Logic |
|--------|-------|
| **Impossible company tenure** | Sarvam AI founded April 2023 → max plausible = 38 months. Krutrim founded Dec 2023 → max plausible = 30 months. Longer claims = fabricated. |
| **3+ expert skills, 0 months used** | Claiming expert in 3+ skills with zero months of use is impossible |
| **12+ expert skills total** | No legitimate candidate has 12+ expert-level skills |
| **5+ advanced/expert skills, 0 months used** | Bulk zero-duration advanced skills = fabricated profile |
| **Inflated total tenure** | Sum of all `duration_months` > 2.5× (`years_of_experience × 12`) |

### Weak Signals (2 required = honeypot)

| Signal | Logic |
|--------|-------|
| 1–2 expert skills with 0 months used | Suspicious but not conclusive alone |
| 10–11 expert skills total | Unusual but some legitimate ML engineers have many |
| 3–4 advanced/expert skills with 0 months | Could be coincidence in small profiles |

### Results

```
Total honeypots detected:  72  (~80 per spec)
Honeypots in top-100:       0  (limit: 10 = 10%)
Honeypot rate in top-100:   0%  ✅
```

### Why Previous Founding-Date Estimates Were Wrong

Initial version incorrectly flagged Saarthi.ai, Rephrase.ai, Locobuzz as "young companies"
when they were founded in 2015–2019. Corrected after auditing company founding dates:

- `Saarthi.ai` — founded 2019 → removed from list (legitimate 5+ year tenures)
- `Rephrase.ai` — founded 2019 → removed
- `Locobuzz` — founded 2015 → removed
- `Sarvam AI` — founded April 2023 → **kept**, max 38 months plausible
- `Krutrim` — founded December 2023 → **kept**, max 30 months plausible

---

## Design Decisions

### Why not semantic embeddings / sentence-transformers?

The compute constraint (≤5 min, CPU-only, no network, no GPU) makes loading a
transformer model risky. `all-MiniLM-L6-v2` takes ~10s to load plus download time.
More critically, the JD itself tells us keyword similarity is the trap:

> *"The right answer involves reasoning about the gap between what the JD says and
> what the JD means."*

A "Marketing Manager" who lists `FAISS` and `Pinecone` as skills will have high
cosine similarity to the JD embedding. Our trust multiplier (endorsements × duration × proficiency)
eliminates this class of false positives with zero model overhead.

### Why behavioral signals as a multiplier rather than additive?

Additive: `0.35×skill + 0.30×career + 0.20×exp + 0.15×behavioral`
→ A score of 0.0 on behavioral (ghost candidate) only reduces final by 15%.

Multiplicative: `base_score × behavioral_multiplier`
→ A multiplier of 0.50 (ghost candidate) halves the score regardless of base.

This matches how a real recruiter thinks: no matter how strong the profile, if the
candidate won't respond, they're not hireable.

### Why a services-company penalty rather than disqualification?

The JD says "entire career at services firms" = bad fit — not "ever worked at one."
A candidate who spent 4 years at Wipro then moved to Flipkart for 5 years still has
valuable product-company experience. Binary disqualification would lose these candidates.
The penalty multiplier (0.85× for mixed backgrounds) preserves them at appropriate ranks.

### Why NDCG@10 gets 50% of the evaluation weight?

Because it does. The spec is explicit. Our calibration focuses the trust multiplier
and title scoring on being harshly discriminating in the top-20, not on gentle
rank-ordering across the full 100. The top-10 should all be unambiguously correct.

### Why hardcode the JD rather than reading from a file?

The spec requires: `has_network_during_ranking: false` and offline execution. Hardcoding
eliminates any risk of file-path issues during Stage 3 Docker reproduction. It also
makes the code auditable — a judge can read exactly what signals are being extracted
from the JD without following any file references.

### Why the soft honeypot penalty (`honeypot_score()`) in addition to hard detection?

Hard detection catches definite honeypots. But there are borderline candidates —
e.g., `too-many-experts=11` without any other signal. These are suspicious but not
definitely fake. The soft penalty applies up to a 50% score reduction proportional
to suspicion score, ensuring borderline cases rank lower without being unfairly zeroed.

---

## Repository Structure

```
redrob-candidate-ranker/
│
├── rank.py                      # ★ Main entrypoint — run this to reproduce submission
├── app.py                       # Streamlit sandbox demo (live at streamlit.app)
├── requirements.txt             # Pinned dependencies (numpy, dateutil, streamlit, pandas)
├── validate_submission.py       # Official format validator (challenge-provided, unmodified)
│
├── leconhinton.csv              # ★ SUBMISSION FILE — top-100 ranked candidates
├── submission_metadata.yaml     # ★ Portal metadata — team info, repo, sandbox link
│
├── candidate_schema.json        # JSON schema for candidate profiles (challenge-provided)
├── sample_candidates.json       # 50-candidate sample for local testing and sandbox demo
│
└── scorer/                      # Scoring engine — all ranking logic lives here
    ├── __init__.py
    │
    ├── jd_parser.py             # Job Description → structured JobDescription object
    │                            #   • 60-entry skill alias/synonym map
    │                            #   • 8 must-have + 5 nice-to-have skill groups
    │                            #   • 35 career description keywords
    │                            #   • 16 ideal job title patterns
    │                            #   • 14 disqualifier company keywords
    │
    ├── honeypot.py              # Impossible profile detector
    │                            #   • Strong/weak signal framework
    │                            #   • 5 detection signals
    │                            #   • Soft suspicion score for borderline cases
    │
    ├── features.py              # Three scoring components
    │                            #   • compute_skill_score()    — trust multiplier
    │                            #   • compute_career_score()   — trajectory + penalty
    │                            #   • compute_experience_score() — YoE + education
    │
    ├── signals.py               # Behavioral signal multiplier [0.50, 1.20]
    │                            #   • 23 Redrob signals → availability × responsiveness
    │                            #   × notice_fit × profile_quality
    │
    ├── ranker.py                # Score assembly + top-N selection
    │                            #   • Weighted combination
    │                            #   • Tie-breaking per spec (candidate_id ascending)
    │                            #   • Progress logging every 20K candidates
    │
    └── reasoning.py             # Per-candidate reasoning string generator
                                 #   • Tier-aware: top (1-25) / mid (26-65) / lower (66-100)
                                 #   • Specific facts only (no hallucination)
                                 #   • 100 guaranteed unique strings
                                 #   • Honest concerns always surfaced
```

---

## Reproduce Submission

### Single command (per spec requirement)

```bash
python rank.py --candidates ./candidates.jsonl --out ./leconhinton.csv
```

### Full reproduce + validate

```bash
# Step 1: Install dependencies
pip install -r requirements.txt

# Step 2: Generate ranked output
python rank.py --candidates ./candidates.jsonl --out ./leconhinton.csv

# Step 3: Validate format
python validate_submission.py leconhinton.csv
# Output: "Submission is valid."
```

### Expected terminal output

```
[1/5] Loading candidates...
  Loaded 10,000 candidates...
  Loaded 20,000 candidates...
  Loaded 30,000 candidates...
  Loaded 40,000 candidates...
  Loaded 50,000 candidates...
  Loaded 60,000 candidates...
  Loaded 70,000 candidates...
  Loaded 80,000 candidates...
  Loaded 90,000 candidates...
  Loaded 100,000 candidates...
  => 100,000 candidates loaded in 4.64s

[2/5] Parsing job description...
  => JD parsed: 8 must-have skills, 5 nice-to-have skills

[3/5] Detecting honeypot candidates...
  => 72 honeypots detected in 1.03s

[4/5] Scoring and ranking candidates...
  Scored 20,000 / 100,000...
  Scored 40,000 / 100,000...
  Scored 60,000 / 100,000...
  Scored 80,000 / 100,000...
  Scored 100,000 / 100,000...
  => Top 100 candidates ranked in 19.29s

[5/5] Generating reasoning strings...
  => Reasoning generated in 0.00s

[OK] Submission written to: leconhinton.csv  (100 rows)
[DONE] Total wall-clock time: 24.88s (OK)
```

### Optional flags

```bash
# Test on sample data
python rank.py --candidates ./sample_candidates.json --out ./test.csv

# Rank top-50 instead of 100
python rank.py --candidates ./candidates.jsonl --out ./out.csv --top-n 50
```

---

## Results — Top 10 Shortlist

All top-10 are ML/AI engineers at product companies with direct production experience
in search, retrieval, ranking, or recommendation systems.

| Rank | Candidate ID | Score | Title | Company | OtW | Resp Rate | Notice |
|------|-------------|-------|-------|---------|-----|-----------|--------|
| 🥇 1 | CAND_0079387 | 0.7828 | AI Engineer | Microsoft | ✅ | 81% | 30d |
| 🥈 2 | CAND_0018499 | 0.7699 | Senior Machine Learning Engineer | Zomato | ✅ | 61% | 15d |
| 🥉 3 | CAND_0064326 | 0.7588 | Search Engineer | Sarvam AI | ✅ | 94% | 45d |
| 4 | CAND_0046064 | 0.7539 | Senior NLP Engineer | Salesforce | ✅ | 78% | 30d |
| 5 | CAND_0036184 | 0.7387 | Recommendation Systems Engineer | CRED | ✅ | 90% | 30d |
| 6 | CAND_0071974 | 0.7325 | Senior AI Engineer | Netflix | ✅ | 76% | 45d |
| 7 | CAND_0027691 | 0.7314 | NLP Engineer | Haptik | ✅ | 68% | 15d |
| 8 | CAND_0046525 | 0.7255 | Senior Machine Learning Engineer | Genpact AI | ✅ | 88% | 60d |
| 9 | CAND_0077337 | 0.7202 | Staff Machine Learning Engineer | Paytm | ✅ | 95% | 60d |
| 10 | CAND_0055905 | 0.7200 | Senior Machine Learning Engineer | Flipkart | ✅ | 87% | 30d |

**Observations:**
- All 10 have `open_to_work = true`
- All 10 are at product companies (none at TCS/Infosys/Wipro/Accenture etc.)
- All 10 have titles directly matching the JD's ideal profile
- Score range for top-100: **0.6093 – 0.7828**
- 72 honeypots detected, **0 appear in top-100**

---

## Submission Files

| File | Purpose | Submit? |
|------|---------|---------|
| `leconhinton.csv` | **Ranked top-100 output** | ✅ Upload this to portal |
| `submission_metadata.yaml` | **Team + repo + sandbox metadata** | ✅ Mirror in portal form |
| `README.md` | Repository documentation | Part of GitHub repo |
| `rank.py` | Reproduce command | Part of GitHub repo |
| `scorer/` | All scoring modules | Part of GitHub repo |

> **Submission filename:** The spec requires filename = registered participant ID.
> Our file is named `leconhinton.csv` matching team name **LeConHinton**.

---

## Compute Environment

| Property | Value |
|----------|-------|
| Platform | MacBook Pro (Apple Silicon M-series) |
| OS | macOS (Darwin arm64) |
| Python | 3.14.3 |
| CPU cores | 8 |
| RAM | 16 GB |
| GPU | **None used** |
| Network during ranking | **None (fully offline)** |
| Wall-clock time | **~25 seconds** for 100K candidates |
| Peak memory | ~1.2 GB |
| Pre-computation | None required |

**Dependencies** (`requirements.txt`):
```
numpy==2.2.6
python-dateutil==2.9.0.post0
streamlit>=1.35.0
pandas>=2.2.0
```

Only `numpy` and `python-dateutil` are required for `rank.py`.
`streamlit` and `pandas` are only needed for `app.py` (the sandbox demo).

---

## AI Tools Declaration

| Tool | How Used |
|------|---------|
| **Kiro (Claude)** | Architecture discussion, planning, code review |

- **No candidate data was fed to any LLM**
- All scoring logic (trust multiplier, services penalty, behavioral multiplier, honeypot detection) was hand-engineered based on analysis of the JD and challenge docs
- The system contains zero LLM API calls and works fully offline
- Code is original work — all design decisions are documented and defensible

---

## Team

**LeConHinton**

| | |
|--|--|
| **GitHub** | https://github.com/neevmodh/redrob-candidate-ranker |
| **Live Demo** | https://redrobai-candidate-ranker.streamlit.app/ |
| **Track** | Track 01 — The Data & AI Challenge: Intelligent Candidate Discovery |
| **Challenge** | Redrob AI Hackathon 2025 |

---

<div align="center">

*Built with Python · Runs in 25 seconds · No GPU · No API calls · No model downloads*

</div>
