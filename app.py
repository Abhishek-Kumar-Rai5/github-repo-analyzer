import os
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from analyzer.pipeline import run_analysis
from analyzer.reporter import to_json, to_markdown, DIFFICULTY_EMOJI

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GitHub Repo Intelligence Analyzer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .obs-item {
        background: #f0f4ff;
        border-left: 4px solid #2563eb;
        padding: 10px 16px;
        margin: 5px 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.93em;
        color: #1e293b;
        line-height: 1.5;
    }
    .badge-beginner {
        background: #16a34a; color: white;
        padding: 4px 14px; border-radius: 20px;
        font-weight: bold; font-size: 0.95em;
    }
    .badge-intermediate {
        background: #ca8a04; color: white;
        padding: 4px 14px; border-radius: 20px;
        font-weight: bold; font-size: 0.95em;
    }
    .badge-advanced {
        background: #dc2626; color: white;
        padding: 4px 14px; border-radius: 20px;
        font-weight: bold; font-size: 0.95em;
    }
    .badge-toonew {
        background: #64748b; color: white;
        padding: 4px 14px; border-radius: 20px;
        font-weight: bold; font-size: 0.95em;
    }
    .conf-high   { color: #16a34a; font-weight: bold; }
    .conf-medium { color: #ca8a04; font-weight: bold; }
    .conf-low    { color: #dc2626; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def diff_badge(difficulty: str) -> str:
    css = {
        "Beginner":     "badge-beginner",
        "Intermediate": "badge-intermediate",
        "Advanced":     "badge-advanced",
        "Too New":      "badge-toonew",
    }.get(difficulty, "badge-toonew")
    emoji = DIFFICULTY_EMOJI.get(difficulty, "?")
    return f'<span class="{css}">{emoji} {difficulty}</span>'


def conf_badge(confidence: str) -> str:
    css = {"HIGH": "conf-high", "MEDIUM": "conf-medium", "LOW": "conf-low"}.get(confidence, "conf-low")
    return f'<span class="{css}">&#9679; {confidence} confidence</span>'


def score_bar(label: str, value: float, max_pts: float):
    pct = min(1.0, float(value) / max_pts) if max_pts else 0.0
    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.progress(pct, text=label)
    with col_b:
        st.markdown(f"**{float(value):.1f}**/{int(max_pts)}")


def make_radar(activity_components: dict) -> go.Figure:
    mapping = {
        "Commit Volume":     ("commit_volume (25pts)",         25),
        "Commit Regularity": ("commit_regularity (20pts)",     20),
        "Issue Resolution":  ("issue_resolution_rate (20pts)", 20),
        "PR Merge Rate":     ("pr_merge_rate (15pts)",         15),
        "Contributors":      ("contributor_health (10pts)",    10),
        "Community":         ("community_signal (10pts)",      10),
    }
    labels = list(mapping.keys())
    values = [
        min(100.0, (activity_components.get(key, 0) / mp) * 100)
        for _, (key, mp) in mapping.items()
    ]
    lc = labels + [labels[0]]
    vc = values + [values[0]]

    fig = go.Figure(go.Scatterpolar(
        r=vc, theta=lc,
        fill="toself",
        line_color="#2563eb",
        fillcolor="rgba(37,99,235,0.18)",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9, gridcolor="#e2e8f0"),
            angularaxis=dict(tickfont_size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=False,
        height=300,
        margin=dict(l=45, r=45, t=25, b=25),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


ACTIVITY_LABELS = {
    "commit_volume (25pts)":         ("Commit Volume",      25),
    "commit_regularity (20pts)":     ("Commit Regularity",  20),
    "issue_resolution_rate (20pts)": ("Issue Resolution",   20),
    "pr_merge_rate (15pts)":         ("PR Merge Rate",      15),
    "contributor_health (10pts)":    ("Contributors",       10),
    "community_signal (10pts)":      ("Community Signal",   10),
}

COMPLEXITY_LABELS = {
    "language_entropy (30pts)":       ("Language Entropy",   30),
    "tech_ecosystem_breadth (25pts)": ("Ecosystem Breadth",  25),
    "codebase_depth_files (20pts)":   ("Codebase Depth",     20),
    "age_normalized_size (15pts)":    ("Age-norm. Size",     15),
    "dependency_surface (10pts)":     ("Dependency Surface", 10),
}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Settings")

    token = st.text_input(
        "GitHub Token (optional)",
        type="password",
        placeholder="ghp_...",
        help=(
            "Without token: 60 req/hr (enough for ~2 repos).\n"
            "With token: 5,000 req/hr.\n"
            "Get one at github.com/settings/tokens — no scopes needed."
        ),
    )
    if not token:
        token = os.getenv("GITHUB_TOKEN", "")

    st.divider()

    workers = st.slider(
        "Parallel fetch threads", 1, 8, 4,
        help="Repos are fetched concurrently. Higher = faster.",
    )

    st.divider()
    st.caption("C2SI WebiU — GSoC 2026 Pre-Task")


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔬 GitHub Repository Intelligence Analyzer")
st.caption("Analyze repositories for activity, structural complexity, and learning difficulty.")

# ── Input ─────────────────────────────────────────────────────────────────────
default_repos = "\n".join([
    "c2siorg/Webiu",
    "c2siorg/GDB-UI",
    "django/django",
    "pallets/flask",
    "torvalds/linux",
])

repo_input = st.text_area(
    "Enter repository URLs — one per line",
    value=default_repos,
    height=150,
    placeholder="https://github.com/django/django\ndjango/django\nowner/repo",
)

btn_col, info_col = st.columns([1, 3])
with btn_col:
    analyze_clicked = st.button("🚀 Analyze", type="primary", use_container_width=True)
with info_col:
    if not token:
        st.warning("No token — rate limited to ~2 repos. Add a token in the sidebar.")
    else:
        st.success("Token set — up to 5,000 API calls/hour.")


# ── Analysis ──────────────────────────────────────────────────────────────────
if analyze_clicked:
    urls = [u.strip() for u in repo_input.strip().splitlines() if u.strip()]
    if not urls:
        st.error("Please enter at least one repository URL.")
        st.stop()

    progress_bar = st.progress(0, text="Starting...")

    def update_progress(current, total, name):
        progress_bar.progress(current / total, text=f"[{current}/{total}] Analyzing {name}...")

    with st.spinner("Fetching repository data..."):
        results = run_analysis(
            urls, token=token, max_workers=workers,
            progress_callback=update_progress,
        )

    progress_bar.progress(1.0, text="Done!")

    if not results:
        st.error("No results returned.")
        st.stop()

    valid   = [r for r in results if not r.error]
    errored = [r for r in results if r.error]

    # ── Summary row ───────────────────────────────────────────────────────
    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Analyzed",        len(valid))
    c2.metric("Beginner",        sum(1 for r in valid if r.difficulty == "Beginner"))
    c3.metric("Intermediate",    sum(1 for r in valid if r.difficulty == "Intermediate"))
    c4.metric("Advanced",        sum(1 for r in valid if r.difficulty == "Advanced"))
    c5.metric("Errors",          len(errored))

    # ── Comparison chart ──────────────────────────────────────────────────
    if len(valid) > 1:
        st.subheader("📊 Comparison")
        df_cmp = pd.DataFrame([{
            "Repository":       r.metrics.full_name,
            "Activity Score":   round(r.activity_score, 1),
            "Complexity Score": round(r.complexity_score, 1),
        } for r in valid])

        fig_cmp = px.bar(
            df_cmp.melt(
                id_vars="Repository",
                value_vars=["Activity Score", "Complexity Score"],
                var_name="Metric", value_name="Score",
            ),
            x="Repository", y="Score", color="Metric",
            barmode="group",
            color_discrete_map={"Activity Score": "#2563eb", "Complexity Score": "#dc2626"},
            height=360,
        )
        fig_cmp.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis_tickangle=-25,
            yaxis_range=[0, 105],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

    # ── Per-repo cards ────────────────────────────────────────────────────
    st.subheader("🔍 Detailed Reports")

    for r in valid:
        m = r.metrics
        emoji = DIFFICULTY_EMOJI.get(r.difficulty, "?")
        header = (
            f"{emoji} **{m.full_name}**  —  "
            f"Activity: {r.activity_score:.1f}  ·  "
            f"Complexity: {r.complexity_score:.1f}  ·  "
            f"{r.difficulty}"
        )

        with st.expander(header, expanded=(len(valid) <= 2)):

            # Row 1: radar | stats
            left, right = st.columns([1, 1])

            with left:
                st.markdown("##### Activity Radar")
                act_comp = r.activity_breakdown.components if r.activity_breakdown else {}
                st.plotly_chart(make_radar(act_comp), use_container_width=True)

                decay = act_comp.get("recency_decay_factor", 1.0)
                raw   = act_comp.get("raw_before_decay", 0)
                st.caption(
                    f"Raw score: {raw:.1f}  ×  "
                    f"Recency decay: {decay:.3f}  =  "
                    f"Final: {r.activity_score:.1f}"
                )

            with right:
                st.markdown("##### Repository Stats")
                s1, s2, s3 = st.columns(3)
                s1.metric("Stars",        f"{m.stars:,}")
                s2.metric("Forks",        f"{m.forks:,}")
                s3.metric("Contributors", m.contributors_count)

                s4, s5, s6 = st.columns(3)
                s4.metric("Commits (30d)",    m.commits_30d)
                s5.metric("Open Issues",      m.open_issues)
                s6.metric("PRs merged (30d)", m.merged_prs_30d)

                s7, s8, s9 = st.columns(3)
                s7.metric("Files",      f"{m.file_count:,}")
                s8.metric("Ecosystems", len(m.tech_ecosystems))
                s9.metric("Age (days)", m.age_days)

                if m.languages:
                    lang_df = pd.DataFrame(
                        list(m.languages.items())[:7],
                        columns=["Language", "Bytes"],
                    )
                    fig_lang = px.pie(
                        lang_df, names="Language", values="Bytes",
                        height=180, hole=0.45,
                    )
                    fig_lang.update_layout(
                        showlegend=True,
                        margin=dict(l=0, r=0, t=8, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        legend=dict(font_size=10),
                    )
                    st.plotly_chart(fig_lang, use_container_width=True)

                if m.tech_ecosystems:
                    st.markdown("**Ecosystems:** " + " · ".join(f"`{e}`" for e in m.tech_ecosystems))
                if m.dependency_files:
                    st.markdown("**Manifests:** " + ", ".join(f"`{f}`" for f in m.dependency_files[:6]))

            # Row 2: score breakdowns
            st.markdown("---")
            bd_l, bd_r = st.columns(2)

            with bd_l:
                st.markdown(f"##### Activity Score — **{r.activity_score:.1f} / 100**")
                if r.activity_breakdown:
                    for raw_key, (label, max_pts) in ACTIVITY_LABELS.items():
                        val = r.activity_breakdown.components.get(raw_key, 0)
                        score_bar(label, val, max_pts)

            with bd_r:
                st.markdown(f"##### Complexity Score — **{r.complexity_score:.1f} / 100**")
                if r.complexity_breakdown:
                    entropy_val = r.complexity_breakdown.components.get("raw_entropy_value", 0)
                    eco_count   = r.complexity_breakdown.components.get("ecosystem_count", 0)
                    st.caption(f"Language entropy: {entropy_val:.3f}  ·  Ecosystems: {eco_count}")
                    for raw_key, (label, max_pts) in COMPLEXITY_LABELS.items():
                        val = r.complexity_breakdown.components.get(raw_key, 0)
                        score_bar(label, val, max_pts)

            # Row 3: difficulty + confidence
            st.markdown("---")
            dc, cc = st.columns(2)
            with dc:
                st.markdown("##### Classification")
                st.markdown(diff_badge(r.difficulty), unsafe_allow_html=True)
            with cc:
                st.markdown("##### Confidence")
                st.markdown(conf_badge(r.confidence), unsafe_allow_html=True)
                if r.confidence != "HIGH" and m.fetch_errors:
                    st.caption(f"Data missing for: {', '.join(m.fetch_errors)}")

            # Row 4: observations
            if r.observations:
                st.markdown("---")
                st.markdown("##### Insights")
                for obs in r.observations:
                    st.markdown(f"> {obs}")

    # ── Errors ────────────────────────────────────────────────────────────
    if errored:
        st.divider()
        st.subheader("Could Not Analyze")
        for r in errored:
            st.error(f"**{r.metrics.url}** — {r.error}")

    # ── Downloads ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Download Reports")
    dl1, dl2 = st.columns(2)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    with dl1:
        st.download_button(
            "Download JSON",
            data=to_json(results),
            file_name=f"repo_analysis_{ts}.json",
            mime="application/json",
            use_container_width=True,
        )
    with dl2:
        st.download_button(
            "Download Markdown",
            data=to_markdown(results),
            file_name=f"repo_analysis_{ts}.md",
            mime="text/markdown",
            use_container_width=True,
        )

else:
    # ── Landing ────────────────────────────────────────────────────────────
    st.info("Enter repository URLs above and click **Analyze** to get started.")

    st.markdown("### How it works")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
**Activity Score**

Measures how alive the repo is *right now*. Looks at commit
volume, commit regularity (cadence, not just count), issue
resolution rate, PR merge rate, and contributor count.
Applies an exponential recency decay — a dormant repo cannot
score high even with great historical numbers.
        """)
    with c2:
        st.markdown("""
**Complexity Score**

Measures how hard the codebase is to understand. Uses Shannon
entropy on language distribution (smarter than raw count),
detects distinct dependency ecosystems, log-scales file count,
and age-normalizes repo size so a rapidly growing new repo
scores higher than an old repo of the same size.
        """)
    with c3:
        st.markdown("""
**Difficulty Classification**

Not a simple threshold. A multi-dimensional decision tree:
Beginner only if complexity is low *and* team is small.
Advanced if complexity is high *or* large active contributor
base. Every result includes a confidence rating
(HIGH / MEDIUM / LOW) based on data completeness.
        """)
