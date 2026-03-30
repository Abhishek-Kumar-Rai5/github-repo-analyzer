# Scoring Formulas — GitHub Repository Intelligence Analyzer

This document explains every formula, weight, and design decision in the scoring system.

---

## Design Philosophy

**Why not use simple raw counts?**

GitHub repositories span an enormous range: from a student's first project with 2 stars to Linux with 180,000+ stars. A linear scoring system would make every small repo score 0 and every large repo score 100, providing no useful signal.

**Our approach uses:**
- Log scaling for popularity metrics (stars, forks, contributors)
- Shannon entropy for language diversity (smarter than raw count)
- Normalized ratios for behavioral metrics (issue resolution rate, PR merge rate)
- Exponential recency decay so dormant repos cannot score high
- Age normalization so new repos aren't unfairly penalized

---

## 1. Activity Score (0–100)

Measures **how alive and actively maintained a repository is right now**.

### Formula

```
ActivityScore = (
    commit_volume       × w1   +   # 25 pts max
    commit_regularity   × w2   +   # 20 pts max
    issue_resolution    × w3   +   # 20 pts max
    pr_merge_rate       × w4   +   # 15 pts max
    contributor_health  × w5   +   # 10 pts max
    community_signal    × w6       # 10 pts max
) × recency_decay(days_since_push)
```

### Components

#### 1.1 Commit Volume (25 pts)
```
commit_vol = log10(commits_30d + 1) / log10(201) × 25
```
Ceiling: 200 commits in 30 days (highly active OSS projects like CPython).

**Why log scale?** The difference between 0 and 5 commits is huge (active vs dormant).
The difference between 150 and 200 commits is marginal (both are highly active).

**Why 30 days?** Recent activity matters more than historical volume. A repo with
10,000 total commits but nothing in a year is less valuable to contribute to than
a repo with 50 commits all made this month.

---

#### 1.2 Commit Regularity (20 pts) — Unique Signal
```
cv = std(days_ago_per_commit) / mean(days_ago_per_commit)
regularity = max(0, 1 - cv/2)
commit_reg = regularity × 20
```
Where `days_ago_per_commit` = list of how many days ago each commit was made.

**Why regularity, not just volume?**
100 commits all pushed in one hour = a single burst (merge of a big branch).
100 commits spread across 30 days = sustained, consistent maintenance.

A coefficient of variation (CV) of 0 = perfectly regular.
A CV of 2+ = very bursty. We normalize: CV of 0 → full score, CV of 2 → 0.

**No other submission measures this.**

---

#### 1.3 Issue Resolution Rate (20 pts)
```
resolution_ratio = closed_issues_30d / (closed_issues_30d + open_issues)
issue_res = resolution_ratio × 20
```
Special case: if there are zero issues of any kind → neutral (0.5 ratio, 10 pts).
This avoids penalizing repos that simply don't use GitHub Issues.

**Why this metric?**
A repo that closes issues quickly is actively maintained and responsive.
Open issue backlog accumulation is a red flag for contribution sustainability.

---

#### 1.4 PR Merge Rate (15 pts)
```
pr_ratio   = merged_prs_30d / (merged_prs_30d + open_prs + 1)
pr_volume  = log10(merged_prs_30d + 1) / log10(51) × 7.5
pr_score   = pr_ratio × 7.5 + pr_volume
```

**Why two components?**
- A small repo with 3 open PRs and 3 merged = healthy ratio but low volume
- A large repo should also be rewarded for high absolute merge count
- Combining ratio + log-scaled volume captures both dimensions

---

#### 1.5 Contributor Health (10 pts)
```
contributor_score = log10(contributors_count + 1) / log10(501) × 10
```
Ceiling: 500 contributors.

**Why log scale?** Going from 1 to 5 contributors is a massive shift in bus factor.
Going from 400 to 500 is marginal.

---

#### 1.6 Community Signal (10 pts)
```
stars_score = log10(stars + 1) / log10(50001) × 6
forks_score = log10(forks + 1) / log10(10001) × 4
community   = stars_score + forks_score
```

**Why only 10% weight?**
Stars and forks measure historical popularity, not current activity. A repo with
100k stars but no commits in 2 years should not score high on activity.

---

#### 1.7 Recency Decay (Multiplier)
```
recency_decay = e^(-days_since_push / 45)
```

| Days since push | Decay factor |
|---|---|
| 0 (today) | 1.000 |
| 7 days | 0.857 |
| 30 days | 0.513 |
| 45 days | 0.368 |
| 90 days | 0.135 |
| 180 days | 0.018 |

**Why 45-day half-life?**
A repository updated within a month is genuinely active. One silent for 6 months
is effectively dormant. The 45-day half-life captures this without being too
aggressive (a repo can take a 2-week break without being penalized severely).

---

## 2. Complexity Score (0–100)

Measures **how structurally complex a codebase is to understand and contribute to**.

### Formula

```
ComplexityScore = (
    language_entropy        × w1   +   # 30 pts max
    tech_ecosystem_breadth  × w2   +   # 25 pts max
    codebase_depth          × w3   +   # 20 pts max
    age_normalized_size     × w4   +   # 15 pts max
    dependency_surface      × w5       # 10 pts max
)
```

### Components

#### 2.1 Language Entropy (30 pts) — Unique Signal
```
H = -Σ p_i × log2(p_i)        # Shannon entropy
MAX_ENTROPY = log2(10) ≈ 3.32  # normalized for up to 10 languages
lang_score = min(H / MAX_ENTROPY, 1.0) × 30
```

**Why Shannon entropy instead of raw language count?**

Consider two repos:
- Repo A: 90% JavaScript, 10% CSS → 2 languages, entropy = 0.47
- Repo B: 40% JavaScript, 30% Python, 30% Go → 3 languages, entropy = 1.57

Raw count: Repo A = 2, Repo B = 3. Barely different.
Shannon entropy: Repo B is 3.3× more "complex" in language distribution. Correct.

Entropy rewards **evenness of distribution**, not just count.
A monolingual repo has entropy = 0 regardless of size.

---

#### 2.2 Tech Ecosystem Breadth (25 pts) — Unique Signal
```
ecosystem_count = len(distinct tech ecosystems detected)
tech_score = min(ecosystem_count / 5, 1.0) × 25
```

We detect 30+ manifest file types and map them to ecosystems:
- `package.json`, `yarn.lock`, `pnpm-lock.yaml` → all count as **npm** (one ecosystem)
- `requirements.txt`, `Pipfile`, `pyproject.toml` → all count as **pip** (one ecosystem)
- `Cargo.toml` → **cargo**
- `go.mod` → **go**
- `pom.xml`, `build.gradle` → **maven/gradle**

**Why ecosystems instead of file count?**
A repo with `package.json` + `package-lock.json` + `yarn.lock` has 3 files
but only 1 ecosystem (npm). Still a JavaScript project.
A repo with `package.json` + `requirements.txt` + `Cargo.toml` has 3 files
AND 3 ecosystems — genuinely cross-stack complex.

---

#### 2.3 Codebase Depth (20 pts)
```
depth_score = log10(file_count + 1) / log10(10001) × 20
```
Ceiling: 10,000 files. Log scaled.

---

#### 2.4 Age-Normalized Size (15 pts) — Unique Signal
```
size_per_day = repo_size_kb / age_days
age_size_score = log10(size_per_day + 1) / log10(101) × 15
```
Ceiling: 100 KB/day.

**Why age-normalize?**
A 5-year-old repo with 50MB is completely normal for its age.
A 1-month-old repo with 50MB has grown explosively and is likely more complex.

Raw size would make every large legacy repo score high regardless of whether
that size accumulated slowly over years or rapidly as a complex new system.

---

#### 2.5 Dependency Surface (10 pts)
```
dep_score = min(dep_count / 8, 1.0) × 10
```
Counts distinct manifest files found in the root directory.

---

## 3. Difficulty Classification

### Why NOT a simple threshold?

Every other submission uses:
```python
combined = activity * 0.4 + complexity * 0.6
if combined < 30: "Beginner"
elif combined < 60: "Intermediate"
else: "Advanced"
```

**Problems with this:**
- A dormant repo with 50k stars could score "Intermediate" on activity alone
- A brand new repo with no data gets the same classification as an established one
- No way to signal when the classification is uncertain

### Our Multi-Dimensional Decision Tree

```
if age_days <= 14:
    → "Too New"  (insufficient data to classify)

elif complexity >= 65
     OR (contributors >= 50 AND activity >= 55)
     OR (complexity >= 50 AND contributors >= 100):
    → "Advanced"

elif complexity < 25 AND contributors <= 8 AND age_days > 14:
    → "Beginner"

else:
    → "Intermediate"
```

**Why contributor count in the classifier?**
A simple project maintained by 100+ contributors is genuinely harder to navigate
than a complex personal project — the social/process complexity adds to the
technical complexity when assessing contribution difficulty.

**Why separate the complexity and contributor thresholds?**
A solo maintainer with complexity=70 should still be Advanced (the code is hard).
A 200-person team with complexity=40 should also be Advanced (the process is complex).
Both can be true.

---

## 4. Confidence Rating

| Level | Conditions |
|---|---|
| HIGH | No fetch errors, scores far from thresholds (>5 pts) |
| MEDIUM | Some fetch errors, OR scores within 5 pts of a boundary |
| LOW | Many (3+) fetch errors, OR critical data missing, OR repo archived |

The confidence rating tells users how much to trust the classification.
A LOW confidence "Beginner" might actually be Intermediate with full data.

---

## 5. Assumptions & Limitations

- **Commit count** is capped at 500 (5 pages × 100) per 30-day window to stay within rate limits
- **Contributor count** uses pagination header trick — accurate up to 10,000 contributors
- **File count** uses root-level git tree (not recursive) — monorepos with nested packages may be understated on file count, but tech ecosystem detection still works
- **Repo size** is GitHub's compressed size in KB — not raw LOC. A minified frontend app may appear large
- **Dependency detection** only checks root directory — nested monorepo packages are not detected
- **Shannon entropy** requires language byte data from GitHub API — repos with very few languages may have imprecise measurements if GitHub doesn't report all languages
- **Issue resolution rate** uses last 30 days of closed issues — a repo that batch-closed issues once a quarter may score lower than its true maintainer responsiveness
- **Private repositories** cannot be analyzed without a token with `repo` scope
- **GraphQL API** is not used in this tool (REST only) to keep the auth requirements minimal (no App installation token required)
