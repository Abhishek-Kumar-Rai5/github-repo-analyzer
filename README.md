# 🔬 GitHub Repository Intelligence Analyzer

A tool that analyzes multiple GitHub repositories and generates structured intelligence reports covering **activity**, **complexity**, and **learning difficulty** — with full scoring transparency, concurrent API fetching, and auto-generated human-readable insights.

## 🚀 Live Demo

👉 **[https://github-repo-analyzer.streamlit.app](https://app-repo-analyzer-jgsdh2hjmwgrbrtpbse3qb.streamlit.app/)**

---

## 📦 Project Structure

```
github-repo-analyzer/
├── analyzer/
│   ├── __init__.py
│   ├── models.py           # RepoMetrics & AnalysisResult dataclasses
│   ├── github_client.py    # GitHub REST API — session reuse, concurrent fetch, ETag cache
│   ├── scoring.py          # All formulas: ActivityScorer, ComplexityScorer, DifficultyClassifier
│   ├── pipeline.py         # Orchestration: parse URLs → fetch → score → return
│   └── reporter.py         # JSON, Markdown, and rich terminal output
├── tests/
│   ├── test_scoring.py     # 29 unit tests for all formula components
│   └── test_pipeline.py    # URL parsing + partial-data pipeline tests
├── sample_outputs/
│   ├── report_full.json    # Full JSON report for 5 repos
│   └── summary_table.md    # Human-readable markdown summary
├── app.py                  # Streamlit web UI
├── cli.py                  # Command-line interface
├── SCORING.md              # Complete formula documentation with rationale
├── requirements.txt
├── render.yaml             # One-click Render deployment
└── .env.example
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.11+
- A GitHub Personal Access Token *(optional but strongly recommended)*
  - Without token: **60 req/hr** — enough for ~2 repos
  - With token: **5,000 req/hr** — enough for 100+ repos
  - Generate at: [github.com/settings/tokens](https://github.com/settings/tokens) *(no special scopes needed)*

### Install

```bash
git clone https://github.com/YOUR_USERNAME/github-repo-analyzer
cd github-repo-analyzer
pip install -r requirements.txt
```

### Configure token (optional but recommended)

```bash
cp .env.example .env
# Edit .env and set GITHUB_TOKEN=ghp_your_token_here
```

Or export directly:
```bash
export GITHUB_TOKEN=ghp_your_token_here   # Linux / macOS
set GITHUB_TOKEN=ghp_your_token_here      # Windows
```

---

## 🖥️ Usage

### Web Interface (Streamlit)

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

Paste repo URLs in the text area, click **Analyze Repositories**. The UI shows:
- Summary metrics (beginner/intermediate/advanced counts)
- Side-by-side comparison bar chart
- Per-repo radar chart of all 6 activity sub-scores
- Expandable score breakdowns with progress bars
- Auto-generated observations panel
- Download buttons (JSON + Markdown reports)

### Command Line

```bash
# Analyze specific repos
python cli.py django/django pallets/flask torvalds/linux

# Full GitHub URLs also work
python cli.py https://github.com/django/django https://github.com/pallets/flask

# Read from a file (one URL per line)
python cli.py --file repos.txt

# Save JSON report
python cli.py django/django pallets/flask --output report.json

# Save Markdown report
python cli.py django/django --markdown report.md

# Both outputs, quiet mode (no table printed)
python cli.py --file repos.txt --output report.json --markdown report.md --quiet

# More concurrent workers (faster, uses more API quota)
python cli.py --file repos.txt --workers 8

# Pass token directly
python cli.py django/django --token ghp_yourtoken

# Debug logging
python cli.py django/django --verbose
```

### Python API

```python
from analyzer import run_analysis, to_json

results = run_analysis(
    ["django/django", "pallets/flask", "c2siorg/Webiu"],
    token="ghp_your_token",
    max_workers=4,
)

for r in results:
    print(f"{r.metrics.full_name}: {r.difficulty} "
          f"(Activity={r.activity_score:.1f}, Complexity={r.complexity_score:.1f}, "
          f"Confidence={r.confidence})")

# Save full JSON report
with open("report.json", "w") as f:
    f.write(to_json(results))
```

### Run Tests

```bash
pytest tests/ -v
```

---

#### 📊 Scoring Formulas (Summary)

> For the complete mathematical rationale, see **[SCORING.md](./SCORING.md)**

### Activity Score (0–100)

Measures how alive and actively maintained a repository is **right now**.

| Component | Max Pts | Formula |
|---|---|---|
| Commit volume (30d) | 25 | `log10(commits_30d + 1) / log10(201) × 25` |
| Commit regularity | 20 | `(1 - CV/2) × 20` where CV = std/mean of commit spacing |
| Issue resolution rate | 20 | `closed_30d / (closed_30d + open) × 20` |
| PR merge rate | 15 | `ratio × 7.5 + log_volume × 7.5` |
| Contributor health | 10 | `log10(contributors + 1) / log10(501) × 10` |
| Community signal | 10 | Log-scaled stars (6pts) + forks (4pts) |
| **Recency decay** | ×multiplier | `e^(-days_since_push / 45)` |

**Key insight:** The recency decay means a dormant repo cannot score high even with great historical metrics. At 90 days of silence, every score is multiplied by 0.135.

### Complexity Score (0–100)

Measures how structurally complex a codebase is to **understand and contribute to**.

| Component | Max Pts | Formula |
|---|---|---|
| Language entropy | 20 | Shannon entropy of language byte distribution |
| Tech ecosystem breadth | 25 | Distinct dependency ecosystems (npm, pip, cargo, make, cmake...) |
| Codebase depth | 28 | `log10(file_count + 1) / log10(10001) × 28` |
| Age-normalized size | 15 | `log10(size_kb/age_days + 1) / log10(101) × 15` |
| Dependency surface | 10 | Count of manifest files in root |
| Scale bonus | 0–15 | Flat bonus for large file counts (≥1k–50k files) and large contributor bases (≥50–500) |

**Key insight:** Shannon entropy distinguishes a repo that is 90% JS + 10% CSS (entropy ≈ 0.47) from one that is 40% JS + 30% Python + 30% Go (entropy ≈ 1.57) — raw language count treats them identically. The scale bonus ensures large single-language systems projects (e.g. Linux: ~96% C, low entropy) still score correctly.

### Difficulty Classification

**Not a simple threshold** — a multi-dimensional decision tree:
```
age ≤ 14 days                                          → Too New
complexity ≥ 55
  OR (contributors ≥ 50 AND activity ≥ 45)
  OR (complexity ≥ 40 AND contributors ≥ 200)
  OR file_count ≥ 50,000
  OR contributors ≥ 500                                → Advanced
complexity < 30
  AND contributors ≤ 5
  AND activity < 40
  AND file_count < 500
  AND stars < 5,000
  AND age > 14 days                                    → Beginner
otherwise                                              → Intermediate
```

Each classification also carries a **confidence rating** (HIGH / MEDIUM / LOW) based on data completeness and proximity to decision boundaries.
---

## 📋 Sample Analysis (5 Repositories)

| Repository | Stars | Activity | Complexity | Difficulty | Confidence |
|---|---|---|---|---|---|
| [c2siorg/Webiu](https://github.com/c2siorg/Webiu) | ⭐ 68 | 38.4 | 22.7 | 🟢 Beginner | HIGH |
| [pallets/flask](https://github.com/pallets/flask) | ⭐ 68,000 | 52.1 | 44.3 | 🟡 Intermediate | HIGH |
| [django/django](https://github.com/django/django) | ⭐ 81,000 | 78.6 | 61.8 | 🔴 Advanced | HIGH |
| [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | ⭐ 340,000 | 21.3 | 8.4 | 🟢 Beginner | HIGH |
| [torvalds/linux](https://github.com/torvalds/linux) | ⭐ 185,000 | 91.2 | 98.7 | 🔴 Advanced | HIGH |

Full reports: [`sample_outputs/report_full.json`](./sample_outputs/report_full.json) · [`sample_outputs/summary_table.md`](./sample_outputs/summary_table.md)

**Key observations:**
- `c2siorg/Webiu` scores **Beginner** — low complexity (4 languages, small codebase), 8 contributors, accessible entry point. Perfect first GSoC repo.
- `sindresorhus/awesome` is **Beginner** despite 340k stars — it's a curated list, not a codebase. Very low complexity, near-zero file count.
- `django/django` is **Advanced** — 61.8 complexity (Python + JS + CSS + templates across 5,000+ files), 100+ contributors, very active.
- `torvalds/linux` hits the ceiling on complexity (98.7) — 70,000+ files across C, Assembly, Python, Shell, and 8+ ecosystems.
- `pallets/flask` is **Intermediate** — actively maintained but architecturally simple (microframework design philosophy).

---

## 🌐 Deployment

### Streamlit Cloud (Recommended — Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → select your repo → set main file to `app.py`
4. Under **Advanced settings → Secrets**, add:
   ```toml
   GITHUB_TOKEN = "ghp_your_token_here"
   ```
5. Click **Deploy** — live in ~2 minutes

### Render (Alternative)

```bash
# Uses render.yaml — one command deploy
# Set GITHUB_TOKEN environment variable in Render dashboard
```

---

## ⚠️ Edge Case Handling

| Scenario | Handling |
|---|---|
| Repository not found (404) | Marked as error in report, analysis continues for other repos |
| Private repository | Same as 404 — error surfaced, analysis continues |
| Rate limit exhausted (403) | Waits for `X-RateLimit-Reset` timestamp, then resumes |
| GitHub 5xx server error | Exponential backoff retry (up to 3 attempts) |
| Zero commits in 30 days | Commit volume = 0, regularity = 0 — still scores other dimensions |
| Zero issues / PRs | Neutral score for those components (not penalized) |
| No language data | Entropy = 0, still scores file count + ecosystem dimensions |
| Missing dependency files | Ecosystem score = 0, other complexity dimensions still scored |
| Repository too new (≤14 days) | Classified "Too New" — insufficient baseline to judge |
| Archived repository | Classified normally but confidence = LOW, observation added |
| Network timeout | Caught per-endpoint — partial data collected, confidence lowered |
| Malformed URL | Parse error surfaced in report, other repos continue |
| Repo with >100k files | File count may be 0 (API truncation) — noted in fetch_errors |

---

## 🛠️ Rate Limit Strategy

- **Authenticated requests** (token): 5,000 req/hr vs 60 unauthenticated
- **ETag / HTTP 304**: If a repo hasn't changed since last fetch in this session, GitHub returns 304 Not Modified — **this costs zero against the rate limit quota**
- **Concurrent fetching**: Multiple repos fetched simultaneously (not sequentially) — faster wall-clock time without additional API calls
- **Proactive quota guard**: When `X-RateLimit-Remaining` drops below 20, the ingestion queue pauses and waits for the reset window
- **Per-endpoint failure isolation**: If one endpoint (e.g., PRs) fails, other endpoints for the same repo are still collected
- **API calls per repo**: ~7 calls (meta, languages, contributors, commits, issues, PRs, file tree) → 5 repos = ~35 calls total

---

## 🔧 Tech Stack

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Rich ecosystem, async-friendly |
| Web UI | Streamlit | Free deployment, fast to build, widely understood |
| Charts | Plotly | Radar chart support, interactive, no JS required |
| Terminal UI | rich | Beautiful CLI tables with color |
| HTTP | `requests` + `ThreadPoolExecutor` | Session reuse + concurrency without async complexity |
| Data | `dataclasses` | Type-safe, zero dependencies |
| Tests | `pytest` | Standard, readable |
| Deployment | Streamlit Cloud | Free tier, 1-click, secrets management |

---
