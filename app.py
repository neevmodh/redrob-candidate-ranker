"""
app.py — Redrob Intelligent Candidate Ranking System
Streamlit sandbox demo for hackathon submission.

Judges can:
  1. Upload a small candidates JSON/JSONL file (≤100 candidates)
  2. Click "Run Ranker"
  3. See the ranked table with scores and reasoning
  4. Download the submission CSV

Deploy to Streamlit Cloud:
  https://share.streamlit.io → connect GitHub repo → set main file = app.py
"""

import io
import json
import csv
import time

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Redrob Candidate Ranker",
    page_icon="🎯",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Lazy import of scorer (only needed when ranking runs)
# ---------------------------------------------------------------------------
@st.cache_resource
def load_pipeline():
    from scorer.jd_parser import get_job_description
    from scorer.honeypot import detect_honeypots
    from scorer.ranker import rank_candidates
    from scorer.reasoning import generate_reasoning
    return get_job_description, detect_honeypots, rank_candidates, generate_reasoning


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("🎯 Redrob Intelligent Candidate Ranker")
st.caption(
    "Hackathon Track 01 — Intelligent Candidate Discovery | "
    "Senior AI Engineer (Founding Team) @ Redrob AI"
)

st.markdown("""
**How it works:**
1. Upload a candidates file (`.json` array or `.jsonl`, max 100 candidates)
2. Click **Run Ranker**
3. View ranked results with per-candidate reasoning
4. Download the submission-ready CSV

> The full pipeline runs on 100K candidates in ~25 seconds on CPU.
> This sandbox demo works on any subset.
""")

st.divider()

# ---------------------------------------------------------------------------
# Job Description preview
# ---------------------------------------------------------------------------
with st.expander("📋 Job Description summary (what we're ranking against)"):
    st.markdown("""
    **Role:** Senior AI Engineer, Founding Team @ Redrob AI (Series A, Pune/Noida)

    **Must-haves:** Production embedding/retrieval systems (sentence-transformers, BGE, E5),
    vector databases (FAISS, Pinecone, Milvus, Qdrant, Weaviate), strong Python,
    evaluation frameworks (NDCG, MRR, A/B testing)

    **Nice-to-haves:** LoRA/QLoRA fine-tuning, learning-to-rank, recommendation systems, MLOps

    **Disqualifiers:** Entire career at TCS/Infosys/Wipro/Accenture/Cognizant, pure research
    without production deployment, CV/speech/robotics without NLP exposure

    **Experience target:** 5–9 years, ideally 6–8 in applied ML at product companies
    """)

# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------
col1, col2 = st.columns([2, 1])

with col1:
    uploaded = st.file_uploader(
        "Upload candidates file",
        type=["json", "jsonl"],
        help="JSON array or JSONL format. Max 100 candidates for the sandbox.",
    )

with col2:
    top_n = st.slider(
        "Top N to rank",
        min_value=5,
        max_value=100,
        value=50,
        step=5,
        help="How many candidates to include in the ranked output",
    )
    show_breakdown = st.checkbox("Show score breakdown", value=False)

# ---------------------------------------------------------------------------
# Load candidates
# ---------------------------------------------------------------------------
candidates = []
load_error = None

if uploaded:
    try:
        content = uploaded.read().decode("utf-8")
        filename = uploaded.name

        if filename.endswith(".jsonl"):
            for lineno, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if line:
                    candidates.append(json.loads(line))
        else:
            data = json.loads(content)
            candidates = data if isinstance(data, list) else [data]

        if len(candidates) > 100:
            st.warning(f"⚠️ File has {len(candidates)} candidates. Truncating to first 100 for the sandbox.")
            candidates = candidates[:100]

        st.success(f"✅ Loaded **{len(candidates)}** candidates from `{filename}`")

    except Exception as e:
        load_error = str(e)
        st.error(f"❌ Failed to parse file: {e}")

# ---------------------------------------------------------------------------
# Run button
# ---------------------------------------------------------------------------
st.divider()

run_disabled = len(candidates) == 0 or load_error is not None
run_btn = st.button("🚀 Run Ranker", type="primary", disabled=run_disabled)

if run_disabled and not uploaded:
    st.info("Upload a candidates file above to get started.")

# ---------------------------------------------------------------------------
# Ranking pipeline
# ---------------------------------------------------------------------------
if run_btn and candidates:
    get_jd, detect_hp, rank_cands, gen_reasoning = load_pipeline()

    progress = st.progress(0, text="Loading pipeline...")
    t_start = time.perf_counter()

    # Stage 1: JD
    progress.progress(10, text="Parsing job description...")
    jd = get_jd()

    # Stage 2: Honeypots
    progress.progress(30, text="Detecting honeypot candidates...")
    hp_ids = detect_hp(candidates)

    # Stage 3: Score + rank
    progress.progress(50, text=f"Scoring {len(candidates)} candidates...")
    actual_top_n = min(top_n, len(candidates))
    ranked = rank_cands(candidates, jd, hp_ids, top_n=actual_top_n)

    # Stage 4: Reasoning
    progress.progress(85, text="Generating reasoning strings...")
    final = gen_reasoning(ranked, jd)

    elapsed = time.perf_counter() - t_start
    progress.progress(100, text="Done!")
    time.sleep(0.3)
    progress.empty()

    # ---- Summary metrics ----
    st.success(f"✅ Ranked **{len(final)}** candidates in **{elapsed:.2f}s**")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Candidates processed", len(candidates))
    m2.metric("Honeypots detected", len(hp_ids))
    m3.metric("Top-N ranked", len(final))
    m4.metric("Wall-clock time", f"{elapsed:.2f}s")

    st.divider()

    # ---- Results table ----
    st.subheader("📊 Ranked Candidates")

    # Build display rows
    display_rows = []
    for item in final:
        c = item["_raw"]
        p = c["profile"]
        sigs = c["redrob_signals"]
        row = {
            "Rank": item["rank"],
            "Candidate ID": item["candidate_id"],
            "Score": round(item["final_score"], 4),
            "Title": p.get("current_title", ""),
            "Company": p.get("current_company", ""),
            "YoE": p.get("years_of_experience", 0),
            "OtW": "✅" if sigs.get("open_to_work_flag") else "❌",
            "Resp Rate": f"{sigs.get('recruiter_response_rate', 0):.0%}",
            "Notice": f"{sigs.get('notice_period_days', 0)}d",
            "Reasoning": item["reasoning"],
        }
        if show_breakdown:
            row["Skill"] = round(item["skill"].get("score", 0), 3)
            row["Career"] = round(item["career"].get("score", 0), 3)
            row["Exp"] = round(item["experience"].get("score", 0), 3)
            row["BehMult"] = round(item["behavioral"].get("multiplier", 1), 3)
        display_rows.append(row)

    # Colour-code top rows
    import pandas as pd
    df = pd.DataFrame(display_rows)

    def highlight_top(row):
        rank = row["Rank"]
        if rank <= 5:
            return ["background-color: #d4edda"] * len(row)
        elif rank <= 20:
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(highlight_top, axis=1),
        use_container_width=True,
        height=600,
    )

    # ---- Detailed reasoning viewer ----
    st.divider()
    st.subheader("🔍 Per-candidate reasoning")
    selected_rank = st.selectbox(
        "Select a rank to inspect",
        options=list(range(1, len(final) + 1)),
        index=0,
    )
    selected = next(item for item in final if item["rank"] == selected_rank)
    sel_c = selected["_raw"]
    sel_p = sel_c["profile"]
    sel_sigs = sel_c["redrob_signals"]

    rc1, rc2 = st.columns(2)
    with rc1:
        st.markdown(f"**Rank #{selected_rank}** — `{selected['candidate_id']}`")
        st.markdown(f"**Title:** {sel_p.get('current_title')} @ {sel_p.get('current_company')}")
        st.markdown(f"**YoE:** {sel_p.get('years_of_experience')} years | "
                    f"**Location:** {sel_p.get('location')}, {sel_p.get('country')}")
        st.markdown(f"**Score:** `{selected['final_score']:.4f}`")
        st.info(f"**Reasoning:** {selected['reasoning']}")

    with rc2:
        st.markdown("**Score breakdown:**")
        sk = selected.get("skill", {})
        ca = selected.get("career", {})
        ex = selected.get("experience", {})
        be = selected.get("behavioral", {})
        bd = be.get("breakdown", {})

        st.markdown(f"- Skill score: `{sk.get('score', 0):.3f}` "
                    f"({sk.get('must_coverage', 0)}/{sk.get('must_total', 8)} must-haves matched)")
        st.markdown(f"- Career score: `{ca.get('score', 0):.3f}` "
                    f"(services penalty: {ca.get('services_penalty', 1):.2f}×)")
        st.markdown(f"- Experience score: `{ex.get('score', 0):.3f}` "
                    f"({ex.get('yoe', 0):.1f} yrs, ML fraction: {ex.get('ml_fraction', 0):.0%})")
        st.markdown(f"- Behavioral multiplier: `{be.get('multiplier', 1):.3f}` "
                    f"(open_to_work: {'✅' if bd.get('open_to_work') else '❌'}, "
                    f"response rate: {bd.get('response_rate', 0):.0%})")
        if selected["candidate_id"] in hp_ids:
            st.error("⚠️ This candidate was flagged as a HONEYPOT")

    # ---- CSV download ----
    st.divider()
    st.subheader("⬇️ Download submission CSV")

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])

    prev_score = None
    for item in final:
        score_out = item["final_score"]
        rank_eps = item["rank"] * 1e-7
        score_out = max(0.0, score_out - rank_eps)
        if prev_score is not None:
            while round(score_out, 4) >= round(prev_score, 4):
                score_out -= 0.00005
            score_out = max(0.0, score_out)
        prev_score = score_out
        writer.writerow([
            item["candidate_id"],
            item["rank"],
            f"{score_out:.4f}",
            item["reasoning"],
        ])

    csv_bytes = csv_buf.getvalue().encode("utf-8")
    st.download_button(
        label="📥 Download submission.csv",
        data=csv_bytes,
        file_name="submission.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Redrob Hackathon 2025 — Track 01: Intelligent Candidate Discovery | "
    "Built with Python + Streamlit | CPU-only, fully offline"
)
