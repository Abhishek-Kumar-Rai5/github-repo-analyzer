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

## Changelog vs v1

| Area | v1 | v2 |
|---|---|---|
| `language_entropy` weight | 30 pts | 20 pts |
| `codebase_depth` weight | 20 pts | 28 pts |
| `scale_bonus` block | — | 0–15 pts (new) |
| Advanced complexity threshold | 65 | 55 |
| Advanced: standalone triggers | — | `file_count >= 50,000` and `contributors >= 500` |
| Advanced: activity requirement | `activity >= 55` | `activity >= 45` (relaxed) |
| Beginner guards | `complexity < 25`, `contributors <= 8` | + `activity < 40`, `file_count < 500`, `stars < 5,000` |
| Ecosystem detection | npm/pip/cargo/go/maven/etc. | + Makefile, CMakeLists.txt, Kconfig, meson.build, Bazel |

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
ComplexityScore = min(100, (
    language_entropy        × w1   +   # 20 pts max  ← reduced from 30 in v1
    tech_ecosystem_breadth  × w2   +   # 25 pts max
    codebase_depth          × w3   +   # 28 pts max  ← increased from 20 in v1
    age_normalized_size     × w4   +   # 15 pts max
    dependency_surface      × w5   +   # 10 pts max
    scale_bonus                        #  0–15 pts   ← new in v2
))
```

Total possible before cap: ~113 pts. Capped at 100.

### Components

#### 2.1 Language Entropy (20 pts) — Reduced from 30 in v1
```
H = -Σ p_i × log2(p_i)        # Shannon entropy
MAX_ENTROPY = log2(10) ≈ 3.32  # normalized for up to 10 languages
lang_score = min(H / MAX_ENTROPY, 1.0) × 20
```
Special case: if no language byte data but `primary_language` is known → 3 pts (minimal credit).

**Why reduced from 30 pts?**
Entropy rewards polyglot repos but is blind to single-language systems projects.
Linux is ~96% C → entropy ≈ 0.3 → `lang_score` ≈ 1.8, yet Linux is objectively
one of the most complex codebases in existence. The new `scale_bonus` (§2.6)
compensates for this. Reducing entropy's weight prevents it from unfairly
*penalizing* systems projects.

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

We detect 40+ manifest file types and map them to ecosystems:
- `package.json`, `yarn.lock`, `pnpm-lock.yaml` → all count as **npm** (one ecosystem)
- `requirements.txt`, `Pipfile`, `pyproject.toml` → all count as **pip** (one ecosystem)
- `Cargo.toml` → **cargo**
- `go.mod` → **go**
- `pom.xml`, `build.gradle` → **maven/gradle**
- `Makefile`, `makefile`, `GNUmakefile` → **make** ← new in v2
- `CMakeLists.txt` → **cmake** ← new in v2
- `Kconfig` → **kbuild** ← new in v2
- `meson.build`, `meson_options.txt` → **meson** ← new in v2
- `BUILD`, `WORKSPACE`, `WORKSPACE.bazel` → **bazel** ← new in v2

**Why ecosystems instead of file count?**
A repo with `package.json` + `package-lock.json` + `yarn.lock` has 3 files
but only 1 ecosystem (npm). Still a JavaScript project.
A repo with `package.json` + `requirements.txt` + `Cargo.toml` has 3 files
AND 3 ecosystems — genuinely cross-stack complex.

**Why add systems build tools in v2?**
Makefile/CMake/Kconfig/Meson/Bazel are the dependency and build management layer
for C, C++, and kernel projects. Excluding them meant systems repos scored
near-zero on tech breadth despite requiring significant toolchain knowledge.

---

#### 2.3 Codebase Depth (28 pts) — Increased from 20 in v1
```
depth_score = log10(file_count + 1) / log10(10001) × 28
```
Ceiling: 10,000 files. Log scaled.

**Why increased from 20 → 28 pts?**
File count is the most universal proxy for navigational complexity — it applies
equally to polyglot web projects and monolingual systems projects. Language entropy
(the previous top-weighted component) cannot distinguish a large C project from a
trivial C project. File count can. Shifting weight here corrects that blind spot.

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

#### 2.6 Scale Bonus (0–15 pts) — New in v2
```
# File count contribution (0–10 pts)
if file_count >= 50,000:  scale_bonus += 10
elif file_count >= 10,000: scale_bonus += 7
elif file_count >= 3,000:  scale_bonus += 4
elif file_count >= 1,000:  scale_bonus += 2

# Contributor count contribution (0–5 pts)
if contributors >= 500:  scale_bonus += 5
elif contributors >= 100: scale_bonus += 3
elif contributors >= 50:  scale_bonus += 1.5
```

**Why a flat bonus instead of continuous scaling?**
The scale bonus exists specifically to ensure that very large single-language
projects (Linux kernel: ~70,000 files, ~5,000 contributors, 96% C) are not
classified as Intermediate due to low entropy. A flat bonus at meaningful
thresholds is more transparent and predictable than continuous scaling.

**Why these two dimensions?**
- **File count** is a direct measure of navigational complexity independent of language.
- **Contributor count** is a proxy for process complexity — understanding how to
  contribute to a 500-person project is harder than contributing to a 5-person project,
  regardless of the code itself.

The maximum combined bonus is 15 pts (10 + 5), bringing the theoretical ceiling
to ~113 pts before the 100-pt cap.

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

### Multi-Dimensional Decision Tree (v2)

```
if age_days <= 14:
    → "Too New"  (insufficient data to classify)

elif (
    complexity >= 55                                    # lowered from 65 in v1
    OR (contributors >= 50 AND activity >= 45)          # activity relaxed from 55
    OR (complexity >= 40 AND contributors >= 200)       # lowered complexity req
    OR file_count >= 50,000                             # NEW: massive codebase
    OR contributors >= 500                              # NEW: huge community
):
    → "Advanced"

elif (
    complexity < 30                                     # raised from 25 in v1
    AND contributors <= 5                               # tightened from 8
    AND activity < 40                                   # NEW guard
    AND file_count < 500                                # NEW guard
    AND stars < 5,000                                   # NEW guard
    AND age_days > 14
):
    → "Beginner"

else:
    → "Intermediate"
```

### What changed from v1, and why?

**Advanced threshold: 65 → 55**
The Linux kernel scores ~51 on complexity (96% C → entropy ≈ 0.3, even with
`scale_bonus`). With the old threshold of 65 it was classified "Intermediate" —
clearly wrong. Lowering to 55 correctly captures large single-language systems
projects.

**Advanced activity requirement: 55 → 45**
Large but slower-moving projects (e.g. mature operating systems, language runtimes)
may sustain 45–54 on activity while still being community-scale projects. The
stricter threshold was incorrectly downgrading them.

**Standalone Advanced triggers (file_count >= 50,000 and contributors >= 500)**
These are unambiguous signals of Advanced difficulty regardless of entropy or
activity score. A repo with 50,000+ files or 500+ contributors presents a
navigational or process challenge no beginner should face as a first contribution.

**Beginner guards (activity, file_count, stars)**
Without these guards, a solo project that happened to be very active, had grown
large, or had accumulated significant community traction could still qualify as
"Beginner" on complexity + contributor count alone. The new guards ensure
"Beginner" means genuinely accessible, not just technically simple.

**Why contributor count in the classifier?**
A simple project maintained by 100+ contributors is genuinely harder to navigate
than a complex personal project — the social/process complexity adds to the
technical complexity when assessing contribution difficulty.

---

## 4. Confidence Rating

| Level | Conditions |
|---|---|
| HIGH | No fetch errors, scores far from thresholds (>5 pts) |
| MEDIUM | Some fetch errors, OR scores within 5 pts of a boundary |
| LOW | Many (3+) fetch errors, OR critical data missing (`repo_meta`, `languages`, `commits`), OR repo archived |

The confidence rating tells users how much to trust the classification.
A LOW confidence "Beginner" might actually be Intermediate with full data.

**Near-threshold boundaries checked (v2):**
- `abs(complexity - 30) < 5` — near Beginner/Intermediate boundary
- `abs(complexity - 55) < 5` — near Intermediate/Advanced boundary (updated from 65)
- `abs(activity - 45) < 5` — near contributor+activity Advanced trigger (updated from 55)

---

## 5. Assumptions & Limitations

- **Commit count** is capped at 500 (5 pages × 100) per 30-day window to stay within rate limits
- **Contributor count** uses pagination header trick — accurate up to 10,000 contributors
- **File count** uses root-level git tree (not recursive) — monorepos with nested packages may be understated on file count, but tech ecosystem detection still works
- **Repo size** is GitHub's compressed size in KB — not raw LOC. A minified frontend app may appear large
- **Dependency detection** only checks root directory — nested monorepo packages are not detected
- **Shannon entropy** requires language byte data from GitHub API — repos with very few languages may have imprecise measurements if GitHub doesn't report all languages
- **Issue resolution rate** uses last 30 days of closed issues — a repo that batch-closed issues once a quarter may score lower than its true maintainer responsiveness
- **Scale bonus** uses root-level file count, so deeply nested monorepos (where most files are in subdirectories) may receive a lower bonus than warranted
- **Systems ecosystem detection** (Makefile, CMakeLists.txt, etc.) is root-directory only — out-of-tree build systems in subdirectories will not be detected
- **Private repositories** cannot be analyzed without a token with `repo` scope
- **GraphQL API** is not used in this tool (REST only) to keep the auth requirements minimal (no App installation token required)
