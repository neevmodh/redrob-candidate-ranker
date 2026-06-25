"""
app.py  -  Redrob AI Candidate Ranker  |  LeConHinton  |  Hackathon 2025
Advanced Streamlit dashboard with full scoring visibility.
"""
import io, json, csv, time
import streamlit as st

st.set_page_config(
    page_title="Redrob AI Ranker - LeConHinton",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""<style>
[data-testid="stMetricValue"]{font-size:1.9rem;font-weight:800;}
[data-testid="stMetricLabel"]{font-size:.78rem;color:#888;}
.hero{background:linear-gradient(135deg,#0d0d1a 0%,#0f2644 60%,#1a0a2e 100%);
      padding:28px 36px;border-radius:18px;margin-bottom:20px;}
.hero h1{color:#e94560;font-size:2.1rem;margin:0;}
.hero p{color:#a8b2d8;margin:6px 0 0;font-size:.95rem;}
.tag{display:inline-block;padding:2px 11px;border-radius:20px;font-size:.75rem;margin:3px 3px 0 0;}
.tag-red{background:#e94560;color:#fff;}
.tag-dark{background:#0f2644;color:#a8b2d8;border:1px solid #e94560;}
.card{background:#f7f9fc;border-radius:14px;padding:18px 20px;
      border-left:5px solid #3498db;margin-bottom:10px;}
.card-hp{border-left-color:#e74c3c!important;background:#fff5f5;}
.card-top{border-left-color:#f39c12!important;background:#fffdf0;}
.sbar-wrap{background:#e0e0e0;border-radius:6px;height:10px;margin:3px 0 6px;}
.sbar-fill{height:10px;border-radius:6px;}
.badge{display:inline-block;padding:2px 9px;border-radius:10px;
       font-size:.75rem;font-weight:700;margin-right:4px;}
.b-gold{background:#FFD700;color:#000;}
.b-silver{background:#aaa;color:#fff;}
.b-bronze{background:#cd7f32;color:#fff;}
.b-blue{background:#3498db;color:#fff;}
.b-green{background:#27ae60;color:#fff;}
.b-red{background:#e74c3c;color:#fff;}
.b-orange{background:#e67e22;color:#fff;}
.sig-good{color:#27ae60;font-weight:700;}
.sig-warn{color:#e67e22;font-weight:700;}
.sig-bad{color:#e74c3c;font-weight:700;}
</style>""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────
def sbar(val: float, color: str = "#27ae60") -> str:
    pct = min(100, int(val * 100))
    return (f'<div class="sbar-wrap"><div class="sbar-fill" '
            f'style="width:{pct}%;background:{color};"></div></div>')

def sig_cls(val, hi=0.65, lo=0.35):
    return "sig-good" if val >= hi else ("sig-warn" if val >= lo else "sig-bad")

def sig_icon(val, hi=0.65, lo=0.35):
    return "🟢" if val >= hi else ("🟡" if val >= lo else "🔴")

def rank_badge_html(rank: int) -> str:
    cls = "b-gold" if rank == 1 else ("b-silver" if rank == 2 else
          ("b-bronze" if rank == 3 else ("b-blue" if rank <= 10 else "b-orange")))
    icon = "🥇" if rank == 1 else ("🥈" if rank == 2 else
           ("🥉" if rank == 3 else ("⭐" if rank <= 10 else "")))
    return f'<span class="badge {cls}">{icon} #{rank}</span>'

GROUP_LABELS = {
    "embeddings": "Embeddings/Retrieval",
    "vector_db": "Vector DB",
    "ranking": "Ranking/IR",
    "eval_framework": "Eval Frameworks",
    "python": "Python",
    "nlp": "NLP/LLM",
    "ml_core": "Core ML",
    "search": "Search Eng.",
    "llm_finetuning": "LLM Fine-tuning",
    "learning_to_rank": "Learning-to-Rank",
    "recsys": "Recsys",
    "mlops": "MLOps",
    "data_eng": "Data Eng.",
}

@st.cache_resource(show_spinner="Loading scoring engine...")
def load_pipeline():
    from scorer.jd_parser import get_job_description
    from scorer.honeypot import detect_honeypots
    from scorer.ranker import rank_candidates
    from scorer.reasoning import generate_reasoning
    return get_job_description, detect_honeypots, rank_candidates, generate_reasoning

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎯 Redrob AI Ranker")
    st.markdown("*LeConHinton · Hackathon 2025*")
    st.divider()
    uploaded = st.file_uploader("📂 Upload Candidates (.json / .jsonl)",
                                 type=["json", "jsonl"])
    top_n = st.slider("Top-N to rank", 5, 100, 50, 5)
    st.divider()
    st.markdown("**View**")
    view_mode = st.radio("", ["🏆 Leaderboard", "🔍 Profile Inspector", "⚔️ Compare 2"],
                         label_visibility="collapsed")
    st.divider()
    st.markdown("**Options**")
    show_charts    = st.checkbox("Show analytics charts", True)
    show_breakdown = st.checkbox("Score breakdown columns", True)
    st.divider()
    st.caption("🔗 [GitHub](https://github.com/neevmodh/redrob-candidate-ranker)")
    st.caption("🌐 [Live Demo](https://redrobai-candidate-ranker.streamlit.app/)")

# ── Hero Header ────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🎯 Redrob AI Candidate Ranker</h1>
  <p>Track 01 · Intelligent Candidate Discovery · Senior AI Engineer @ Redrob AI (Series A)</p>
  <div style="margin-top:12px;">
    <span class="tag tag-red">CPU-only</span>
    <span class="tag tag-dark">No API calls</span>
    <span class="tag tag-dark">~25s on 100K candidates</span>
    <span class="tag tag-dark">72 honeypots detected</span>
    <span class="tag tag-dark">All 23 signals used</span>
  </div>
</div>""", unsafe_allow_html=True)

# ── JD Expander ────────────────────────────────────────────────────────────
with st.expander("📋 Job Description — what we're ranking against"):
    jc1, jc2, jc3 = st.columns(3)
    with jc1:
        st.markdown("**✅ Must-Have (8 groups)**")
        for s in ["Embeddings · Dense Retrieval", "FAISS / Pinecone / Milvus",
                  "BM25 · Hybrid Search", "NDCG / MRR / A-B Testing",
                  "Strong Python", "NLP / LLMs / RAG",
                  "Core ML (PyTorch / sklearn)", "Search Engineering"]:
            st.markdown(f"- {s}")
    with jc2:
        st.markdown("**⭐ Nice-to-Have (5 groups)**")
        for s in ["LoRA / QLoRA Fine-tuning", "Learning-to-Rank",
                  "Recommendation Systems", "MLOps / MLflow", "Data Engineering"]:
            st.markdown(f"- {s}")
    with jc3:
        st.markdown("**❌ Disqualifiers**")
        for s in ["Entire career at TCS / Infosys / Wipro",
                  "Pure research, no production",
                  "CV/Speech primary, no NLP",
                  "Title-chasing (avg <18mo tenure)",
                  "LangChain-only AI experience"]:
            st.markdown(f"- {s}")
    st.info("**Ideal:** 6–8 yrs applied ML · product companies · Pune/Noida hybrid · notice ≤30d")

# ── Load candidates ────────────────────────────────────────────────────────
candidates, load_error = [], None
if uploaded:
    try:
        raw = uploaded.read().decode("utf-8")
        if uploaded.name.endswith(".jsonl"):
            candidates = [json.loads(l) for l in raw.splitlines() if l.strip()]
        else:
            d = json.loads(raw)
            candidates = d if isinstance(d, list) else [d]
        if len(candidates) > 100:
            candidates = candidates[:100]
            st.sidebar.warning("Truncated to 100 for sandbox")
        st.sidebar.success(f"✅ {len(candidates)} candidates ready")
    except Exception as e:
        load_error = str(e)
        st.sidebar.error(f"❌ {e}")

if not uploaded:
    st.info("👈 Upload **sample_candidates.json** from the sidebar to test the ranker.")

# ── Session state ─────────────────────────────────────────────────────────
for key in ("results", "hp_ids", "jd", "elapsed", "n_total"):
    if key not in st.session_state:
        st.session_state[key] = None

# ── Run button + pipeline ─────────────────────────────────────────────────
run_btn = st.button("🚀  Run Ranker", type="primary",
                    disabled=(not candidates or bool(load_error)),
                    use_container_width=True)

if run_btn and candidates:
    get_jd, detect_hp, rank_cands, gen_reason = load_pipeline()
    bar, stat = st.progress(0), st.empty()
    t0 = time.perf_counter()
    stat.info("**[1/4]** Parsing job description…"); bar.progress(8)
    jd = get_jd()
    stat.info("**[2/4]** Detecting honeypot candidates…"); bar.progress(28)
    hp_ids = detect_hp(candidates)
    stat.info(f"**[3/4]** Scoring {len(candidates)} candidates…"); bar.progress(55)
    ranked = rank_cands(candidates, jd, hp_ids, top_n=min(top_n, len(candidates)))
    stat.info("**[4/4]** Generating reasoning strings…"); bar.progress(85)
    final = gen_reason(ranked, jd)
    elapsed = time.perf_counter() - t0
    bar.progress(100); time.sleep(0.15); bar.empty(); stat.empty()
    st.session_state.update(results=final, hp_ids=hp_ids, jd=jd,
                             elapsed=elapsed, n_total=len(candidates))
    st.success(f"✅ Done in **{elapsed:.2f}s** — {len(final)} candidates ranked")

# ══════════════════════════════════════════════════════════════════════════
# RESULTS SECTION
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.results:
    final   = st.session_state.results
    hp_ids  = st.session_state.hp_ids
    jd      = st.session_state.jd
    elapsed = st.session_state.elapsed
    n_total = st.session_state.n_total
    import pandas as pd

    # ── KPI Row ───────────────────────────────────────────────────────────
    st.divider()
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Candidates",      n_total)
    k2.metric("Ranked",          len(final))
    k3.metric("Honeypots",       len(hp_ids), delta=f"{len(hp_ids)/n_total*100:.0f}%", delta_color="inverse")
    k4.metric("Runtime",         f"{elapsed:.2f}s")
    k5.metric("Top Score",       f"{final[0]['final_score']:.4f}" if final else "—")
    avg_top10 = sum(r["final_score"] for r in final[:10]) / min(10, len(final))
    k6.metric("Avg Top-10 Score",f"{avg_top10:.4f}")
    st.divider()

    # ── Analytics charts ──────────────────────────────────────────────────
    if show_charts:
        scores  = [r["final_score"]                          for r in final]
        ranks   = [r["rank"]                                 for r in final]
        s_sk    = [r.get("skill",{}).get("score",0)          for r in final]
        s_ca    = [r.get("career",{}).get("score",0)         for r in final]
        s_ex    = [r.get("experience",{}).get("score",0)     for r in final]
        s_bm    = [r.get("behavioral",{}).get("multiplier",1) for r in final]
        cos     = [r["_raw"]["profile"]["current_company"]   for r in final]
        locs    = [r["_raw"]["profile"].get("country","")    for r in final]

        df_c = pd.DataFrame({"Rank":ranks,"Score":scores,"Skill":s_sk,
                              "Career":s_ca,"Exp":s_ex,"BehMult":s_bm,
                              "Company":cos,"Country":locs})

        ca,cb = st.columns(2)
        with ca:
            st.markdown("##### 📊 Score Distribution")
            st.bar_chart(df_c.set_index("Rank")["Score"], height=240)
        with cb:
            st.markdown("##### 🧩 Component Breakdown — Top 20")
            st.bar_chart(df_c.head(20).set_index("Rank")[["Skill","Career","Exp"]], height=240)

        cc,cd = st.columns(2)
        with cc:
            st.markdown("##### 🏢 Companies in Shortlist")
            st.bar_chart(df_c["Company"].value_counts().head(10), height=200)
        with cd:
            st.markdown("##### 🌍 Candidate Countries")
            st.bar_chart(df_c["Country"].value_counts().head(8), height=200)
        st.divider()

    # ── VIEW: Leaderboard ────────────────────────────────────────────────
    if view_mode == "🏆 Leaderboard":
        st.subheader("🏆 Ranked Shortlist")
        rows = []
        for item in final:
            p   = item["_raw"]["profile"]
            sig = item["_raw"]["redrob_signals"]
            sk  = item.get("skill",{})
            ca  = item.get("career",{})
            ex  = item.get("experience",{})
            be  = item.get("behavioral",{})
            row = {
                "Rank":       item["rank"],
                "Score":      round(item["final_score"],4),
                "Title":      p.get("current_title",""),
                "Company":    p.get("current_company",""),
                "YoE":        p.get("years_of_experience",0),
                "Location":   p.get("location",""),
                "OtW":        "✅" if sig.get("open_to_work_flag") else "❌",
                "RespRate":   f"{sig.get('recruiter_response_rate',0):.0%}",
                "Notice":     f"{sig.get('notice_period_days',0)}d",
                "HP":         "⚠️" if item["candidate_id"] in hp_ids else "✅",
                "Reasoning":  item["reasoning"],
            }
            if show_breakdown:
                row["Skill"]   = round(sk.get("score",0),3)
                row["Career"]  = round(ca.get("score",0),3)
                row["Exp"]     = round(ex.get("score",0),3)
                row["BehX"]    = round(be.get("multiplier",1),3)
                row["Must"]    = f"{sk.get('must_coverage',0)}/{sk.get('must_total',8)}"
            rows.append(row)

        df = pd.DataFrame(rows)

        def _row_color(row):
            if row["HP"] == "⚠️":
                return ["background-color:#fff0f0"]*len(row)
            r = row["Rank"]
            if r<=3:   return ["background-color:#fffde7"]*len(row)
            if r<=10:  return ["background-color:#f0fff4"]*len(row)
            if r<=25:  return ["background-color:#f0f4ff"]*len(row)
            return [""]*len(row)

        def _score_color(v):
            if not isinstance(v,float): return ""
            if v>=0.75: return "color:#27ae60;font-weight:800"
            if v>=0.60: return "color:#e67e22;font-weight:700"
            if v<=0.35: return "color:#e74c3c"
            return ""

        styled = df.style.apply(_row_color, axis=1)
        score_cols = ["Score"]
        if show_breakdown:
            score_cols += ["Skill","Career","Exp","BehX"]
        styled = styled.map(_score_color, subset=score_cols)
        st.dataframe(styled, use_container_width=True, height=600)

    # ── VIEW: Profile Inspector ──────────────────────────────────────────
    elif view_mode == "🔍 Profile Inspector":
        st.subheader("🔍 Deep-Dive Profile Inspector")
        options = {f"#{r['rank']} · {r['_raw']['profile']['current_title']} @ "
                   f"{r['_raw']['profile']['current_company']} [{r['candidate_id']}]": r
                   for r in final}
        sel_label = st.selectbox("Select candidate", list(options.keys()))
        item = options[sel_label]
        c   = item["_raw"]
        p   = c["profile"]
        sig = c["redrob_signals"]
        sk  = item.get("skill",{})
        ca  = item.get("career",{})
        ex  = item.get("experience",{})
        be  = item.get("behavioral",{})
        bd  = be.get("breakdown",{})
        dp  = item.get("disqualifier",{})
        is_hp = item["candidate_id"] in hp_ids

        # Header card
        card_cls = "card-hp" if is_hp else ("card-top" if item["rank"]<=10 else "card")
        st.markdown(f"""
<div class="{card_cls}">
  {rank_badge_html(item['rank'])}
  {'<span class="badge b-red">⚠️ HONEYPOT</span>' if is_hp else '<span class="badge b-green">✅ Clean</span>'}
  <span class="badge b-blue">{item['candidate_id']}</span>
  <h3 style="margin:10px 0 4px;">{p.get('current_title','?')}
    <span style="color:#888;font-size:.85rem;font-weight:400">@ {p.get('current_company','?')}</span>
  </h3>
  <p style="margin:0;color:#555;">
    📍 {p.get('location','?')}, {p.get('country','?')} &nbsp;|&nbsp;
    🎓 {p.get('years_of_experience',0):.1f} years exp &nbsp;|&nbsp;
    🏭 {p.get('current_industry','?')}
  </p>
  <p style="margin:6px 0 0;font-style:italic;color:#777;font-size:.88rem;">
    "{p.get('headline','')}"
  </p>
</div>""", unsafe_allow_html=True)

        # Score summary
        sc1,sc2,sc3,sc4,sc5 = st.columns(5)
        sc1.metric("Final Score",    f"{item['final_score']:.4f}")
        sc2.metric("Skill Score",    f"{sk.get('score',0):.3f}")
        sc3.metric("Career Score",   f"{ca.get('score',0):.3f}")
        sc4.metric("Exp Score",      f"{ex.get('score',0):.3f}")
        sc5.metric("Beh Multiplier", f"{be.get('multiplier',1):.3f}")

        st.markdown(f"**Reasoning:** {item['reasoning']}")
        st.divider()

        # Three columns: skills | career | signals
        pi1, pi2, pi3 = st.columns([1,1,1])

        with pi1:
            st.markdown("#### 🛠️ Skills")
            must_matched  = set(sk.get("matched_must",[]))
            nice_matched  = set(sk.get("matched_nice",[]))
            all_skills    = c.get("skills",[])
            for s in all_skills[:15]:
                sname = s.get("name","")
                dur   = int(s.get("duration_months") or 0)
                end   = int(s.get("endorsements") or 0)
                prof  = s.get("proficiency","beginner")
                from scorer.jd_parser import normalise_skill
                grp   = normalise_skill(sname)
                is_must = grp in must_matched
                is_nice = grp in nice_matched
                prof_colors = {"expert":"#27ae60","advanced":"#3498db",
                               "intermediate":"#e67e22","beginner":"#aaa"}
                col = prof_colors.get(prof,"#aaa")
                flag = " ✅" if is_must else (" ⭐" if is_nice else "")
                st.markdown(
                    f'<div style="margin:3px 0;font-size:.85rem;">'
                    f'<span style="color:{col};font-weight:600;">{sname}</span>{flag}'
                    f'<br><span style="color:#888;font-size:.75rem;">'
                    f'{prof} · {dur}mo · {end} endorsements</span>'
                    f'{sbar(min(dur/48,1), col)}</div>',
                    unsafe_allow_html=True)
            st.caption(f"Must-haves matched: {sk.get('must_coverage',0)}/{sk.get('must_total',8)}")
            if sk.get("matched_nice"):
                nice_labels = [GROUP_LABELS.get(g,g) for g in sk["matched_nice"]]
                st.caption(f"Nice-to-haves: {', '.join(nice_labels)}")

        with pi2:
            st.markdown("#### 💼 Career")
            st.markdown(f"**Title score:** {ca.get('title_score',0):.2f} "
                        f"({sig_icon(ca.get('title_score',0),0.7,0.4)})")
            st.markdown(f"**Career desc score:** {ca.get('desc_score',0):.2f} "
                        f"({sig_icon(ca.get('desc_score',0),0.5,0.25)})")
            svc = ca.get("services_fraction",0)
            pen = ca.get("services_penalty",1)
            svc_col = "#e74c3c" if svc>0.7 else ("#e67e22" if svc>0.3 else "#27ae60")
            st.markdown(
                f'<span style="color:{svc_col};font-weight:700;">'
                f'Services fraction: {svc:.0%} → {pen:.2f}× penalty</span>',
                unsafe_allow_html=True)
            st.markdown("---")
            for i, role in enumerate(c.get("career_history",[])[:5]):
                curr = "🔵" if role.get("is_current") else "⚪"
                dur  = int(role.get("duration_months") or 0)
                st.markdown(
                    f'{curr} **{role.get("title","")}** @ {role.get("company","")}  '
                    f'*({dur}mo · {role.get("industry","")})*')
            edu = c.get("education",[])
            if edu:
                st.markdown("---")
                st.markdown("**Education**")
                for e in edu[:2]:
                    tier = e.get("tier","?")
                    st.markdown(f"🎓 {e.get('degree','')} {e.get('field_of_study','')} "
                                f"· {e.get('institution','')} [{tier}]")

            # Disqualifier flags
            if dp and dp.get("flags"):
                st.markdown("---")
                st.error("**⚠️ Disqualifier flags:**")
                for f in dp["flags"]:
                    st.markdown(f"- {f}")

        with pi3:
            st.markdown("#### 📡 Behavioral Signals")
            # Open to work + recency
            otw = sig.get("open_to_work_flag", False)
            days = bd.get("days_since_active", 999)
            st.markdown(
                f'**Open to work:** <span class="{"sig-good" if otw else "sig-bad"}">'
                f'{"YES ✅" if otw else "NO ❌"}</span>',
                unsafe_allow_html=True)
            st.markdown(
                f'**Last active:** <span class="{sig_cls(1-min(days/270,1),0.5,0.2)}">'
                f'{int(days)} days ago</span>',
                unsafe_allow_html=True)
            rr = sig.get("recruiter_response_rate",0)
            st.markdown(
                f'**Recruiter resp rate:** <span class="{sig_cls(rr)}">{rr:.0%}</span>',
                unsafe_allow_html=True)
            notice = int(sig.get("notice_period_days",0))
            nc = "#27ae60" if notice<=30 else ("#e67e22" if notice<=60 else "#e74c3c")
            st.markdown(
                f'**Notice period:** <span style="color:{nc};font-weight:700;">{notice} days</span>',
                unsafe_allow_html=True)
            st.markdown("---")
            # Numeric signals as mini bars
            sigs_to_show = [
                ("Availability",  bd.get("availability",0)),
                ("Responsiveness",bd.get("responsiveness",0)),
                ("Hunt Intent",   bd.get("hunt_intent",0)),
                ("Role Fit",      bd.get("role_fit",0)),
                ("Profile Quality",bd.get("profile_quality",0)),
            ]
            for label, val in sigs_to_show:
                col = "#27ae60" if val>=0.65 else ("#e67e22" if val>=0.35 else "#e74c3c")
                st.markdown(
                    f'<div style="font-size:.8rem;margin:3px 0;">'
                    f'<span style="font-weight:600;">{label}</span> '
                    f'<span style="color:{col};font-weight:700;">{val:.2f}</span>'
                    f'{sbar(val, col)}</div>',
                    unsafe_allow_html=True)
            st.markdown("---")
            # Extra signals
            gh = sig.get("github_activity_score",-1)
            wfm = sig.get("preferred_work_mode","?")
            wr  = sig.get("willing_to_relocate",False)
            apps = sig.get("applications_submitted_30d",0)
            views = sig.get("profile_views_received_30d",0)
            saved = sig.get("saved_by_recruiters_30d",0)
            sal = sig.get("expected_salary_range_inr_lpa",{})
            st.markdown(f"GitHub score: **{gh if gh>=0 else 'not linked'}**")
            st.markdown(f"Work mode: **{wfm}** · Relocate: **{'Yes ✅' if wr else 'No ❌'}**")
            st.markdown(f"Apps (30d): **{apps}** · Profile views: **{views}** · Saved: **{saved}**")
            if sal:
                st.markdown(f"Salary: **₹{sal.get('min',0):.0f}–{sal.get('max',0):.0f} LPA**")

    # ── VIEW: Compare 2 ─────────────────────────────────────────────────
    elif view_mode == "⚔️ Compare 2":
        st.subheader("⚔️ Side-by-Side Candidate Comparison")
        rank_choices = [f"#{r['rank']} · {r['_raw']['profile']['current_title']} @ "
                        f"{r['_raw']['profile']['current_company']}" for r in final]
        cc1, cc2 = st.columns(2)
        with cc1:
            sel_a = st.selectbox("Candidate A", rank_choices, index=0, key="ca")
        with cc2:
            sel_b = st.selectbox("Candidate B", rank_choices,
                                  index=min(1, len(rank_choices)-1), key="cb")

        idx_a = rank_choices.index(sel_a)
        idx_b = rank_choices.index(sel_b)
        ia, ib = final[idx_a], final[idx_b]

        def _compare_col(item, col_key):
            c   = item["_raw"]
            p   = c["profile"]
            sig = c["redrob_signals"]
            sk  = item.get("skill",{})
            ca  = item.get("career",{})
            ex  = item.get("experience",{})
            be  = item.get("behavioral",{})
            bd  = be.get("breakdown",{})
            is_hp = item["candidate_id"] in hp_ids

            col_key.markdown(
                f'<div class="{"card-hp" if is_hp else "card"}">'
                f'{rank_badge_html(item["rank"])} '
                f'{"<span class=\'badge b-red\'>⚠️ HP</span>" if is_hp else ""}'
                f'<h4 style="margin:8px 0 2px;">{p.get("current_title","")}</h4>'
                f'<div style="color:#555;font-size:.85rem;">{p.get("current_company","")} · '
                f'{p.get("location","")} · {p.get("years_of_experience",0):.1f} yrs</div>'
                f'</div>',
                unsafe_allow_html=True)

            # Score comparison bars
            metrics = [
                ("Final Score",   item["final_score"],       1.0,  "#e94560"),
                ("Skill",         sk.get("score",0),         1.0,  "#3498db"),
                ("Career",        ca.get("score",0),         1.0,  "#27ae60"),
                ("Experience",    ex.get("score",0),         1.0,  "#9b59b6"),
                ("Beh Multiplier",be.get("multiplier",1)/1.25,1.0,  "#f39c12"),
            ]
            for label, val, mx, color in metrics:
                display = val * 1.25 if label == "Beh Multiplier" else val
                col_key.markdown(
                    f'<div style="margin:5px 0;font-size:.85rem;">'
                    f'<b>{label}</b>: <span style="color:{color};font-weight:800;">'
                    f'{display:.3f}</span>'
                    f'{sbar(val, color)}</div>',
                    unsafe_allow_html=True)

            col_key.markdown("**Must-haves matched:**")
            for g in sk.get("matched_must",[]):
                col_key.markdown(f"  ✅ {GROUP_LABELS.get(g,g)}")
            for g in (set(["embeddings","vector_db","ranking","eval_framework",
                           "python","nlp","ml_core","search"])
                      - set(sk.get("matched_must",[]))):
                col_key.markdown(f"  ❌ {GROUP_LABELS.get(g,g)}")

            col_key.markdown(f"**Open to work:** {'✅ Yes' if sig.get('open_to_work_flag') else '❌ No'}")
            col_key.markdown(f"**Response rate:** {sig.get('recruiter_response_rate',0):.0%}")
            col_key.markdown(f"**Notice:** {sig.get('notice_period_days',0)}d")
            col_key.markdown(f"**Reasoning:** *{item['reasoning']}*")

        comp_a, comp_b = st.columns(2)
        _compare_col(ia, comp_a)
        _compare_col(ib, comp_b)

    # ── CSV Download ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("⬇️ Download Submission CSV")
    dl1, dl2 = st.columns([2,1])
    with dl1:
        buf = io.StringIO()
        wr  = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        wr.writerow(["candidate_id","rank","score","reasoning"])
        prev = None
        for item in final:
            s = max(0.0, item["final_score"] - item["rank"]*1e-7)
            if prev is not None:
                while round(s,4) >= round(prev,4):
                    s -= 0.00005
                s = max(0.0, s)
            prev = s
            wr.writerow([item["candidate_id"], item["rank"],
                         f"{s:.4f}", item["reasoning"]])
        csv_bytes = buf.getvalue().encode("utf-8")
        st.download_button("📥 Download submission CSV",
                           data=csv_bytes,
                           file_name="leconhinton.csv",
                           mime="text/csv",
                           use_container_width=True)
    with dl2:
        st.info(f"**{len(final)} rows** · Spec-compliant format · "
                f"Non-increasing scores · Tie-break by cand_id asc")

    # ── Honeypots section ─────────────────────────────────────────────────
    if hp_ids:
        with st.expander(f"⚠️ {len(hp_ids)} Honeypot Candidates Detected (forced below top-100)"):
            hp_in_top = [r for r in final if r["candidate_id"] in hp_ids]
            if hp_in_top:
                st.error(f"{len(hp_in_top)} honeypots still in ranked output — review scoring.")
            else:
                st.success("All honeypots successfully excluded from top-100.")
            st.caption("Detection signals: impossible company tenure (Sarvam AI/Krutrim), "
                       "3+ expert skills with 0 months, 12+ expert skills, inflated tenure ratios.")

# ── Footer ─────────────────────────────────────────────────────────────────
st.divider()
fc1, fc2, fc3 = st.columns(3)
fc1.caption("🎯 **Redrob AI Hackathon 2025** · Track 01")
fc2.caption("👥 **Team:** LeConHinton")
fc3.caption("🔗 [GitHub](https://github.com/neevmodh/redrob-candidate-ranker) · "
            "[Streamlit](https://redrobai-candidate-ranker.streamlit.app/)")
