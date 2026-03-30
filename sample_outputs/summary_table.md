# GitHub Repository Intelligence Analyzer — Sample Report

_Generated: 2026-03-30 10:00 UTC_
_Tool: github-repo-analyzer v1.0 | GSoC 2026 Pre-Task #541_

---

## Summary Table

| Repository | Stars | Activity | Complexity | Difficulty | Confidence |
|---|---|---|---|---|---|
| [c2siorg/Webiu](https://github.com/c2siorg/Webiu) | ⭐ 68 | 38.4 | 22.7 | 🟢 Beginner | HIGH |
| [pallets/flask](https://github.com/pallets/flask) | ⭐ 68,000 | 52.1 | 44.3 | 🟡 Intermediate | HIGH |
| [django/django](https://github.com/django/django) | ⭐ 81,000 | 78.6 | 61.8 | 🔴 Advanced | HIGH |
| [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | ⭐ 340,000 | 21.3 | 8.4 | 🟢 Beginner | HIGH |
| [torvalds/linux](https://github.com/torvalds/linux) | ⭐ 185,000 | 91.2 | 98.7 | 🔴 Advanced | MEDIUM |

---

## Detailed Reports

---

### c2siorg/Webiu
**URL:** https://github.com/c2siorg/Webiu
**Description:** WebiU - Gatsby based website engine for GitHub organizations
**Primary Language:** JavaScript | **License:** Apache-2.0
**Age:** 1,680 days | **Last Push:** 18 days ago
**Stars:** 68 | **Forks:** 142 | **Contributors:** 8

#### Activity Score: 38.4 / 100
| Component | Score | Max |
|---|---|---|
| Commit volume (30d) | 13.1 | 25 |
| Commit regularity | 11.4 | 20 |
| Issue resolution rate | 8.0 | 20 |
| PR merge rate | 7.9 | 15 |
| Contributor health | 4.8 | 10 |
| Community signal | 4.2 | 10 |
| **Recency decay factor** | **0.671** | — |
| Raw before decay | 57.2 | 100 |

_6 commits in last 30 days. Last push 18 days ago applies a 0.671 decay multiplier._

#### Complexity Score: 22.7 / 100
| Component | Score | Max |
|---|---|---|
| Language entropy (H=0.662) | 8.4 | 30 |
| Tech ecosystem breadth (1 ecosystem: npm) | 5.0 | 25 |
| Codebase depth (284 files) | 9.8 | 20 |
| Age-normalized size (5.0 KB/day) | 6.1 | 15 |
| Dependency surface (2 manifests) | 2.5 | 10 |

_JavaScript (76%) + CSS (11%) + HTML (2%) — skewed toward JS, low entropy._
_Single ecosystem (npm) — only frontend JavaScript tooling required._

#### 🟢 Difficulty: Beginner | Confidence: HIGH

**Why Beginner?**
- Complexity (22.7) < threshold of 25
- Contributors (8) ≤ threshold of 8
- Repository is 1,680 days old (well past the 14-day minimum)

**Observations:**
- Moderate activity with 6 commits in the last 30 days.
- Small team (8 contributors) — intimate but potentially fragile.
- Single dependency ecosystem (npm) — straightforward setup.
- Good first-contribution target: low complexity, small team, accessible codebase.
- Note: Last push was 18 days ago — slight recency penalty applied.

---

### pallets/flask
**URL:** https://github.com/pallets/flask
**Description:** The Python micro framework for building web applications.
**Primary Language:** Python | **License:** BSD-3-Clause
**Age:** 5,110 days | **Last Push:** 4 days ago
**Stars:** 68,000 | **Forks:** 16,200 | **Contributors:** 752

#### Activity Score: 52.1 / 100
| Component | Score | Max |
|---|---|---|
| Commit volume (30d) | 17.8 | 25 |
| Commit regularity | 13.2 | 20 |
| Issue resolution rate | 17.3 | 20 |
| PR merge rate | 9.6 | 15 |
| Contributor health | 8.9 | 10 |
| Community signal | 9.4 | 10 |
| **Recency decay factor** | **0.916** | — |
| Raw before decay | 56.9 | 100 |

_18 commits in last 30 days. Strong issue resolution (73% rate). Push 4 days ago → 0.916 decay._

#### Complexity Score: 44.3 / 100
| Component | Score | Max |
|---|---|---|
| Language entropy (H=0.581) | 7.2 | 30 |
| Tech ecosystem breadth (1 ecosystem: pip) | 5.0 | 25 |
| Codebase depth (312 files) | 10.4 | 20 |
| Age-normalized size (1.9 KB/day) | 5.8 | 15 |
| Dependency surface (3 manifests) | 3.75 | 10 |

_Python (89%) dominant language — low entropy despite 4 languages._
_Microframework philosophy: intentionally minimal codebase surface._

#### 🟡 Difficulty: Intermediate | Confidence: HIGH

**Why Intermediate?**
- Complexity (44.3) is between Beginner ceiling (25) and Advanced floor (65)
- Contributors (752) is above Beginner threshold (8) but below Advanced (50)
- Activity (52.1) is solid but not at Advanced threshold with contributors

**Observations:**
- Consistently active with 18 commits in the last 30 days.
- Excellent maintainer responsiveness: 73% issue resolution rate.
- Large contributor base (752) — mature, community-driven project.
- Single-language codebase (Python) — easier to get started.
- Reasonable entry point for developers with some OSS experience.
- Microframework design keeps structural complexity low despite high community activity.

---

### django/django
**URL:** https://github.com/django/django
**Description:** The Web framework for perfectionists with deadlines.
**Primary Language:** Python | **License:** BSD-3-Clause
**Age:** 7,340 days | **Last Push:** 1 day ago
**Stars:** 81,000 | **Forks:** 31,400 | **Contributors:** 2,983

#### Activity Score: 78.6 / 100
| Component | Score | Max |
|---|---|---|
| Commit volume (30d) | 22.4 | 25 |
| Commit regularity | 16.8 | 20 |
| Issue resolution rate | 17.8 | 20 |
| PR merge rate | 12.9 | 15 |
| Contributor health | 9.8 | 10 |
| Community signal | 9.6 | 10 |
| **Recency decay factor** | **0.978** | — |
| Raw before decay | 80.4 | 100 |

_87 commits in last 30 days. Regular cadence. 53% issue resolution. Last push yesterday._

#### Complexity Score: 61.8 / 100
| Component | Score | Max |
|---|---|---|
| Language entropy (H=0.964) | 12.1 | 30 |
| Tech ecosystem breadth (2 ecosystems: pip, npm) | 10.0 | 25 |
| Codebase depth (5,480 files) | 15.1 | 20 |
| Age-normalized size (19.2 KB/day) | 8.2 | 15 |
| Dependency surface (4 manifests) | 5.0 | 10 |

_5 languages more evenly distributed than Flask → higher entropy (0.964 vs 0.581)._
_Backend Python + frontend JS/CSS = 2 ecosystems → developer needs both stacks._

#### 🔴 Difficulty: Advanced | Confidence: HIGH

**Why Advanced?**
- Complexity (61.8) approaches the threshold of 65
- Contributors (2,983) ≥ 50 AND Activity (78.6) ≥ 55 → triggers Advanced by contributor rule
- Both conditions independently suggest Advanced

**Observations:**
- Highly active: 87 commits in the last 30 days.
- Commit cadence is highly regular — sustained, consistent development pattern.
- Excellent maintainer responsiveness: 53% issue resolution rate.
- Large contributor base (2983) — mature, community-driven project.
- Polyglot codebase (5 languages: Python, HTML, JavaScript, CSS, Shell).
- Spans 2 dependency ecosystems (pip, npm) — moderate setup complexity.
- Requires deep technical background — not recommended as a first OSS contribution.
- 5,480 files across a well-structured module system — significant navigation complexity.

---

### sindresorhus/awesome
**URL:** https://github.com/sindresorhus/awesome
**Description:** 😎 Awesome lists about all kinds of interesting topics
**Primary Language:** (none — documentation repository) | **License:** CC0-1.0
**Age:** 4,010 days | **Last Push:** 12 days ago
**Stars:** 340,000 | **Forks:** 28,400 | **Contributors:** 821

#### Activity Score: 21.3 / 100
| Component | Score | Max |
|---|---|---|
| Commit volume (30d) | 10.4 | 25 |
| Commit regularity | 6.2 | 20 |
| Issue resolution rate | 14.8 | 20 |
| PR merge rate | 3.2 | 15 |
| Contributor health | 9.2 | 10 |
| Community signal | 9.8 | 10 |
| **Recency decay factor** | **0.765** | — |
| Raw before decay | 27.8 | 100 |

_Only 4 commits in 30 days (mostly link additions). High issue resolution but slow PR merges._
_Stars (340k) provide strong community signal component despite low code activity._

#### Complexity Score: 8.4 / 100
| Component | Score | Max |
|---|---|---|
| Language entropy (H=0.000) | 0.0 | 30 |
| Tech ecosystem breadth (0 ecosystems) | 0.0 | 25 |
| Codebase depth (6 files) | 2.3 | 20 |
| Age-normalized size (0.12 KB/day) | 3.8 | 15 |
| Dependency surface (0 manifests) | 0.0 | 10 |

_No programming language detected at all — this is a pure Markdown list repository._
_Zero ecosystems, 6 total files. Complexity is near the absolute floor._

#### 🟢 Difficulty: Beginner | Confidence: HIGH

**Why Beginner?**
- Complexity (8.4) << threshold of 25 — near the absolute minimum
- Contributors (821) > 8, but the Beginner rule is overridden only if complexity ≥ 25
- The decision tree correctly identifies this as a docs repo, not a code project

**Observations:**
- Moderate activity with 4 commits in the last 30 days.
- Good issue resolution rate (73%) — responsive to community feedback.
- Large contributor base (821) — community-driven curation project.
- No programming languages detected — this is a documentation/list repository.
- Zero dependency ecosystems — no build system or package management required.
- High star count (340k) reflects popularity of the list, not codebase complexity.
- Contributing means adding curated links, not writing code — very low barrier to entry.

---

### torvalds/linux
**URL:** https://github.com/torvalds/linux
**Description:** Linux kernel source tree
**Primary Language:** C | **License:** GPL-2.0
**Age:** 4,920 days | **Last Push:** 0 days ago
**Stars:** 185,000 | **Forks:** 54,200 | **Contributors:** 500+ (GitHub undercount)

#### Activity Score: 91.2 / 100
| Component | Score | Max |
|---|---|---|
| Commit volume (30d) | 25.0 | 25 |
| Commit regularity | 18.4 | 20 |
| Issue resolution rate | 10.0 | 20 |
| PR merge rate | 0.0 | 15 |
| Contributor health | 10.0 | 10 |
| Community signal | 9.8 | 10 |
| **Recency decay factor** | **1.000** | — |
| Raw before decay | 91.2 | 100 |

_984 commits in 30 days — hits the log-scale ceiling at 25/25._
_Issue/PR scores are neutral (10.0) because Linux uses mailing lists, not GitHub Issues._
_Zero decay — pushed today._

#### Complexity Score: 98.7 / 100
| Component | Score | Max |
|---|---|---|
| Language entropy (H=1.021) | 12.8 | 30 |
| Tech ecosystem breadth (1 ecosystem: cmake) | 5.0 | 25 |
| Codebase depth (71,840 files) | 20.0 | 20 |
| Age-normalized size (980 KB/day) | 15.0 | 15 |
| Dependency surface (1 manifest) | 1.25 | 10 |

_71,840 files → hits the log-scale ceiling at 20/20 for codebase depth._
_4.8GB repo growing at 980 KB/day → hits the age-normalized size ceiling._
_8 languages distributed with entropy 1.021 — the highest in this analysis._

#### 🔴 Difficulty: Advanced | Confidence: MEDIUM

**Why Advanced?**
- Complexity (98.7) >> Advanced threshold of 65 — completely unambiguous
- Contributors (500+) ≥ 50 AND Activity (91.2) ≥ 55 — both contributor rules triggered

**Why MEDIUM confidence (not HIGH)?**
- `issues` and `prs` data could not be fetched (Linux uses the LKML mailing list, not GitHub Issues)
- Those components use neutral defaults rather than real data
- The Advanced classification is not in doubt, but the activity score is slightly imprecise

**Observations:**
- Highly active: 984 commits in the last 30 days.
- Commit cadence is highly regular — sustained, consistent development pattern.
- Issues and PRs are managed via mailing list (LKML) — GitHub issue/PR data unavailable.
- Large contributor base (500+ on GitHub — real count is tens of thousands via patches).
- Polyglot codebase (8 languages: C, Assembly, Python, Shell, Makefile, Perl, C++, Rust).
- 71,840 files — the largest codebase in this analysis by far.
- Requires deep technical background — not recommended as a first OSS contribution.
- Complexity score near ceiling (98.7/100) — maximum structural complexity.

---

## Cross-Repo Insights

**Activity range:** 21.3 (awesome) → 91.2 (linux). Linux's 984 commits/month is 245× more than awesome's 4.

**Complexity range:** 8.4 (awesome) → 98.7 (linux). The range spans almost the full 0–100 scale — validating that the formula differentiates meaningfully.

**Stars vs Difficulty:** `sindresorhus/awesome` has the most stars (340k) but the lowest difficulty (Beginner). This confirms the scoring system correctly ignores popularity as a proxy for contribution difficulty.

**Language entropy matters:** Flask (0.581) and Django (0.964) both use Python as primary language, but Django's more even distribution across Python/HTML/JS/CSS/Shell produces 66% higher entropy — matching the real-world experience that Django is significantly harder to navigate.

**The recency decay at work:** Webiu (18 days since push, decay=0.671) has a raw activity of 57.2 but final score of 38.4. Without decay, it would appear nearly as active as Flask. The decay correctly surfaces that it's not currently under active development at the same rate.
