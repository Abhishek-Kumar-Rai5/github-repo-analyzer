"""
scoring.py — Activity Score, Complexity Score, and Difficulty Classifier.

Design philosophy:
  - Every formula component is independently testable
  - Log scaling handles the enormous variance between repos (1 star vs 100k stars)
  - Shannon entropy for language distribution (smarter than raw language count)
    BUT weighted less than before — entropy alone cannot capture systems projects
  - Commit cadence regularity (not just volume)
  - Issue resolution rate as maintainer responsiveness proxy
  - Age normalization: new repos aren't penalized unfairly
  - Codebase scale bonus: catches large single-language systems projects
    (Linux, Redis, SQLite) that score low on entropy but are objectively complex
  - Multi-dimensional difficulty classifier with confidence rating

Changelog vs v1:
  - language_entropy weight: 30 → 20 pts  (entropy ≠ difficulty for systems projects)
  - codebase_depth weight:   20 → 28 pts  (file count is a more universal scale signal)
  - Added scale_bonus block  (0–15 pts)   (file_count + contributor thresholds)
  - Advanced complexity threshold: 65 → 55
  - Advanced: added file_count >= 50,000 and contributors >= 500 as standalone triggers
  - Beginner: added activity < 40 and file_count < 500 and stars < 5,000 guards
  - Ecosystem detection expanded: Makefile, CMakeLists.txt, Kconfig, meson.build, Bazel

See SCORING.md for full mathematical rationale.
"""

import math
import statistics
from datetime import datetime, timezone
from .models import RepoMetrics, ScoreBreakdown, AnalysisResult


# ── Utility functions ─────────────────────────────────────────────────────────

def _log_scale(value: float, ceiling: float, max_pts: float) -> float:
    """
    Log-scale a value to max_pts points.
    log10(value+1) / log10(ceiling+1) × max_pts

    Why log scaling?
      The difference between 1 and 100 stars is meaningful.
      The difference between 50,000 and 100,000 stars is less so.
      Log scaling compresses the upper range fairly.
    """
    if value <= 0:
        return 0.0
    return min(math.log10(value + 1) / math.log10(ceiling + 1), 1.0) * max_pts


def _linear_scale(value: float, ceiling: float, max_pts: float) -> float:
    """Linear scale, capped at ceiling."""
    if value <= 0:
        return 0.0
    return min(value / ceiling, 1.0) * max_pts


def _shannon_entropy(language_bytes: dict) -> float:
    """
    Compute Shannon entropy of language distribution.
    H = -Σ p_i × log2(p_i)

    Why Shannon entropy instead of raw language count?
      A repo that is 90% JS + 10% CSS has entropy ≈ 0.47 — simple.
      A repo that is 40% JS + 30% Python + 30% Go has entropy ≈ 1.57 — genuinely complex.
      Raw language count would score them identically (both have "multiple languages").

    LIMITATION: entropy alone cannot capture systems projects written in a single
    dominant language (Linux = 96% C → entropy ≈ 0.3 despite being highly complex).
    The scale_bonus in ComplexityScorer compensates for this.

    Returns: entropy value (0 = single language, higher = more evenly distributed)
    Max theoretical value: log2(N) where N = number of languages
    """
    if not language_bytes:
        return 0.0
    total = sum(language_bytes.values())
    if total == 0:
        return 0.0
    probs = [v / total for v in language_bytes.values() if v > 0]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def _commit_regularity_score(commit_dates_iso: list, max_pts: float = 20.0) -> float:
    """
    Score how regularly commits are spread across 30 days.

    Why regularity matters?
      100 commits all pushed in one day = a burst (less healthy signal).
      100 commits spread evenly across 30 days = consistent maintenance.

    Method: convert dates to day-of-month, compute coefficient of variation.
    Low CV = more regular = higher score.

    Returns: 0–max_pts
    """
    if len(commit_dates_iso) < 2:
        return 0.0

    days = []
    for iso in commit_dates_iso:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            day_ago = (now - dt).days
            days.append(day_ago)
        except Exception:
            pass

    if len(days) < 2:
        return max_pts * 0.3  # Partial credit

    mean = statistics.mean(days)
    std = statistics.stdev(days)
    if mean == 0:
        return max_pts * 0.3  # Partial credit only

    cv = std / mean
    regularity = max(0.0, 1.0 - (cv / 2.0))
    return regularity * max_pts


def _recency_decay(days_since_push: int) -> float:
    """
    Exponential decay factor based on days since last push.
    f(d) = e^(-d/45)

    Values:
      0 days  → 1.00 (full score)
      30 days → 0.51
      45 days → 0.37
      90 days → 0.13
      180 days → 0.02 (near zero)

    Why 45-day half-life?
      A repo updated within a month is active.
      A repo silent for 6 months is essentially dormant.
    """
    return math.exp(-days_since_push / 45.0)


def _detect_ecosystems(dependency_files: list) -> list:
    """
    Map dependency/manifest filenames to canonical ecosystem names.
    Multiple files from the same ecosystem count as ONE ecosystem.

    Expanded in v2 to include systems-programming build systems:
      Makefile, CMakeLists.txt, Kconfig → make/cmake/kbuild
      meson.build → meson
      BUILD / WORKSPACE → bazel

    Returns: list of distinct ecosystem strings.
    """
    MANIFEST_TO_ECOSYSTEM = {
        # JavaScript / Node
        "package.json":         "npm",
        "yarn.lock":            "npm",
        "pnpm-lock.yaml":       "npm",
        "package-lock.json":    "npm",
        ".npmrc":               "npm",
        # Python
        "requirements.txt":     "pip",
        "Pipfile":              "pip",
        "Pipfile.lock":         "pip",
        "pyproject.toml":       "pip",
        "setup.py":             "pip",
        "setup.cfg":            "pip",
        # Rust
        "Cargo.toml":           "cargo",
        "Cargo.lock":           "cargo",
        # Go
        "go.mod":               "go",
        "go.sum":               "go",
        # Java / Kotlin
        "pom.xml":              "maven",
        "build.gradle":         "gradle",
        "build.gradle.kts":     "gradle",
        "settings.gradle":      "gradle",
        # Ruby
        "Gemfile":              "gem",
        "Gemfile.lock":         "gem",
        # PHP
        "composer.json":        "composer",
        "composer.lock":        "composer",
        # .NET / C#
        "*.csproj":             "nuget",
        "*.fsproj":             "nuget",
        "packages.config":      "nuget",
        # Swift / ObjC
        "Podfile":              "cocoapods",
        "Package.swift":        "spm",
        # Dart / Flutter
        "pubspec.yaml":         "pub",
        # Elixir
        "mix.exs":              "hex",
        # Haskell
        "stack.yaml":           "stack",
        "*.cabal":              "cabal",
        # Docker
        "Dockerfile":           "docker",
        "docker-compose.yml":   "docker",
        "docker-compose.yaml":  "docker",
        # Nix
        "flake.nix":            "nix",
        "default.nix":          "nix",
        # Systems / C / C++ build systems  ← NEW in v2
        "Makefile":             "make",
        "makefile":             "make",
        "GNUmakefile":          "make",
        "CMakeLists.txt":       "cmake",
        "Kconfig":              "kbuild",
        "meson.build":          "meson",
        "meson_options.txt":    "meson",
        "BUILD":                "bazel",
        "WORKSPACE":            "bazel",
        "WORKSPACE.bazel":      "bazel",
        # Terraform / Infrastructure
        "*.tf":                 "terraform",
        # Ansible
        "playbook.yml":         "ansible",
    }

    ecosystems = set()
    for fname in dependency_files:
        # Exact match first
        if fname in MANIFEST_TO_ECOSYSTEM:
            ecosystems.add(MANIFEST_TO_ECOSYSTEM[fname])
            continue
        # Wildcard suffix match
        for pattern, eco in MANIFEST_TO_ECOSYSTEM.items():
            if pattern.startswith("*") and fname.endswith(pattern[1:]):
                ecosystems.add(eco)
                break

    return list(ecosystems)


# ── Activity Scorer ───────────────────────────────────────────────────────────

class ActivityScorer:
    """
    Measures how alive and actively maintained a repository is right now.

    Score components (total = 100 pts before decay):
      commit_volume      25 pts  — raw commits in last 30 days (log scaled)
      commit_regularity  20 pts  — how evenly commits are spread (unique signal)
      issue_resolution   20 pts  — closed/(closed+open) ratio = maintainer responsiveness
      pr_merge_rate      15 pts  — PRs actually getting merged = code moving forward
      contributor_health 10 pts  — team size (log scaled)
      community_signal   10 pts  — stars + forks (log scaled, weak signal)

    Final score: weighted_sum × recency_decay(days_since_push)
    A dormant repo cannot score high even with great historical metrics.
    """

    def score(self, m: RepoMetrics) -> ScoreBreakdown:
        bd = ScoreBreakdown()

        # 1. Commit volume (25 pts) — log scaled, ceiling at 200 commits/30d
        commit_vol = _log_scale(m.commits_30d, 200, 25.0)

        # 2. Commit regularity (20 pts)
        commit_reg = _commit_regularity_score(m.commit_dates_30d, 20.0)
        if m.commits_30d == 0:
            commit_reg = 0.0

        # 3. Issue resolution rate (20 pts)
        total_issue_activity = m.closed_issues_30d + max(m.open_issues, 0)
        if total_issue_activity > 0:
            resolution_ratio = m.closed_issues_30d / total_issue_activity
        else:
            resolution_ratio = 0.5  # neutral — repo may not use GitHub Issues
        issue_res = resolution_ratio * 20.0

        # 4. PR merge rate (15 pts)
        if m.open_prs + m.merged_prs_30d > 0:
            pr_ratio = m.merged_prs_30d / (m.merged_prs_30d + max(m.open_prs, 1))
        else:
            pr_ratio = 0.0
        pr_volume = _log_scale(m.merged_prs_30d, 50, 7.5)
        pr_score = (pr_ratio * 7.5) + pr_volume

        # 5. Contributor health (10 pts) — log scaled, ceiling at 500
        contributor_score = _log_scale(m.contributors_count, 500, 10.0)

        # 6. Community signal (10 pts) — log scaled stars + forks
        stars_score = _log_scale(m.stars, 50000, 6.0)
        forks_score = _log_scale(m.forks, 10000, 4.0)
        community = stars_score + forks_score

        raw_total = commit_vol + commit_reg + issue_res + pr_score + contributor_score + community

        # Apply recency decay — dormant repos cannot score high
        decay = _recency_decay(m.days_since_push)
        final = min(100.0, raw_total * decay)

        bd.components = {
            "commit_volume (25pts)":        round(commit_vol, 2),
            "commit_regularity (20pts)":    round(commit_reg, 2),
            "issue_resolution_rate (20pts)": round(issue_res, 2),
            "pr_merge_rate (15pts)":        round(pr_score, 2),
            "contributor_health (10pts)":   round(contributor_score, 2),
            "community_signal (10pts)":     round(community, 2),
            "recency_decay_factor":         round(decay, 3),
            "raw_before_decay":             round(raw_total, 2),
        }
        bd.total = round(final, 2)
        return bd


# ── Complexity Scorer ─────────────────────────────────────────────────────────

class ComplexityScorer:
    """
    Measures how structurally complex a codebase is to understand and contribute to.

    Score components (total = 100 pts):
      language_entropy    20 pts  — Shannon entropy of language distribution
                                    (reduced from 30 → entropy ≠ difficulty for
                                     single-language systems projects like Linux/Redis)
      tech_breadth        25 pts  — number of distinct dependency ecosystems
      codebase_depth      28 pts  — log-scaled file count
                                    (increased from 20 → most universal scale signal)
      age_normalized_size 15 pts  — repo_size_kb / age_days
      dependency_surface  10 pts  — count of distinct manifest files
      scale_bonus       0–15 pts  — flat bonus for very large file counts and
                                    very large contributor counts; compensates for
                                    single-language systems projects that score low
                                    on entropy but are objectively hard to navigate

    Total possible: ~113 pts, capped at 100.

    v2 Changes:
      - language_entropy: 30 → 20 pts
      - codebase_depth:   20 → 28 pts
      - Added scale_bonus block
      - Ecosystem detection expanded (see _detect_ecosystems)
    """

    # Maximum expected entropy for normalization (~log2(10 languages) = 3.32)
    MAX_ENTROPY = math.log2(10)

    def score(self, m: RepoMetrics) -> ScoreBreakdown:
        bd = ScoreBreakdown()

        # 1. Language entropy (20 pts) — reduced from 30
        #    Entropy rewards polyglot repos but cannot distinguish a large C project
        #    from a trivial C project. scale_bonus compensates below.
        entropy = _shannon_entropy(m.languages)
        lang_score = min(entropy / self.MAX_ENTROPY, 1.0) * 20.0
        if not m.languages and m.primary_language:
            lang_score = 3.0  # Single confirmed language — minimal credit

        # 2. Tech breadth — distinct ecosystems (25 pts)
        #    Use _detect_ecosystems() to collapse multiple files into one ecosystem.
        #    Expanded in v2 to include Makefile, CMakeLists.txt, Kconfig, Bazel, Meson.
        ecosystems = _detect_ecosystems(m.dependency_files)
        ecosystem_count = len(ecosystems)
        tech_score = _linear_scale(ecosystem_count, 5, 25.0)

        # 3. Codebase depth — file count (28 pts) — increased from 20
        #    Log scaled, ceiling at 10,000 files.
        #    This is the most universal proxy for navigational complexity.
        depth_score = _log_scale(m.file_count, 10000, 28.0)

        # 4. Age-normalized size (15 pts)
        #    size_per_day = repo_size_kb / age_days
        #    A 1-month-old 50MB repo is more unusual than a 5-year-old 50MB repo.
        if m.age_days > 0:
            size_per_day = m.repo_size_kb / m.age_days
        else:
            size_per_day = 0
        age_size_score = _log_scale(size_per_day, 100, 15.0)

        # 5. Dependency surface (10 pts)
        dep_count = len(m.dependency_files)
        dep_score = _linear_scale(dep_count, 8, 10.0)

        # 6. Scale bonus (0–15 pts) — NEW in v2
        #    Flat bonus for properties that reliably indicate Advanced complexity
        #    regardless of language distribution:
        #      a) Very large file counts (10k+ files = massive, 3k+ = significant)
        #      b) Very large contributor bases (process complexity compounds technical)
        #    This ensures Linux (70k files, 5k contributors) scores Advanced even though
        #    it is ~96% C (entropy ≈ 0.3, lang_score ≈ 1.8 — nearly nothing).
        scale_bonus = 0.0

        if m.file_count >= 50000:
            scale_bonus += 10.0
        elif m.file_count >= 10000:
            scale_bonus += 7.0
        elif m.file_count >= 3000:
            scale_bonus += 4.0
        elif m.file_count >= 1000:
            scale_bonus += 2.0

        if m.contributors_count >= 500:
            scale_bonus += 5.0
        elif m.contributors_count >= 100:
            scale_bonus += 3.0
        elif m.contributors_count >= 50:
            scale_bonus += 1.5

        total = lang_score + tech_score + depth_score + age_size_score + dep_score + scale_bonus

        bd.components = {
            "language_entropy (20pts)":     round(lang_score, 2),
            "tech_ecosystem_breadth (25pts)": round(tech_score, 2),
            "codebase_depth_files (28pts)": round(depth_score, 2),
            "age_normalized_size (15pts)":  round(age_size_score, 2),
            "dependency_surface (10pts)":   round(dep_score, 2),
            "scale_bonus (0-15pts)":        round(scale_bonus, 2),
            "raw_entropy_value":            round(entropy, 4),
            "ecosystem_count":              ecosystem_count,
            "ecosystems_detected":          ecosystems,
        }
        bd.total = round(min(100.0, total), 2)
        return bd


# ── Difficulty Classifier ─────────────────────────────────────────────────────

class DifficultyClassifier:
    """
    Multi-dimensional classification — NOT a simple combined score threshold.

    v1 Problem:
      The original thresholds (Advanced: complexity >= 65) were too high.
      The Linux kernel scores ~51 on complexity because it is 96% C (low entropy),
      even though it has 70,000+ files and 5,000+ contributors.
      Result: Linux was classified "Intermediate" — clearly wrong.

    v2 Fix:
      - Advanced complexity threshold: 65 → 55
      - Added standalone Advanced triggers: file_count >= 50,000 and
        contributors >= 500 (process complexity alone = Advanced)
      - Relaxed contributor threshold for Advanced: 50 AND activity >= 45
        (was activity >= 55 — too strict for large but slower projects)
      - Beginner: added activity < 40, file_count < 500, stars < 5,000 guards
        to prevent mis-classifying legitimate Intermediate solo projects

    Decision tree:

      TOO NEW:      age_days <= 14
      ADVANCED:     complexity >= 55
                    OR (contributors >= 50 AND activity >= 45)
                    OR (complexity >= 40 AND contributors >= 200)
                    OR file_count >= 50,000          ← NEW
                    OR contributors >= 500           ← NEW
      BEGINNER:     complexity < 30
                    AND contributors <= 5
                    AND activity < 40               ← NEW
                    AND file_count < 500            ← NEW
                    AND stars < 5,000               ← NEW
                    AND age_days > 14
      INTERMEDIATE: everything else

    Confidence rating:
      HIGH:   all key metrics available, scores far from thresholds (>5 pts)
      MEDIUM: some fetch errors OR scores within 5 pts of a threshold
      LOW:    many fetch errors OR repo archived / missing data
    """

    def classify(self, activity: float, complexity: float, m: RepoMetrics) -> tuple[str, str]:
        """Returns (difficulty_label, confidence_level)."""

        # ── Determine difficulty ──────────────────────────────────────────────

        is_advanced = (
            complexity >= 55                                        # lowered from 65
            or (m.contributors_count >= 50 and activity >= 45)     # relaxed activity req
            or (complexity >= 40 and m.contributors_count >= 200)  # lowered complexity
            or m.file_count >= 50000                               # NEW: massive codebase
            or m.contributors_count >= 500                         # NEW: huge community
        )

        is_beginner = (
            complexity < 30                    # slightly raised from 25
            and m.contributors_count <= 5      # tightened from 8
            and activity < 40                  # NEW: can't be secretly very active
            and m.file_count < 500             # NEW: even a solo project with 2k files isn't Beginner
            and m.stars < 5000                 # NEW: highly starred repos have earned some credibility
            and m.age_days > 14
        )

        if m.age_days <= 14:
            difficulty = "Too New"
        elif is_advanced:
            difficulty = "Advanced"
        elif is_beginner:
            difficulty = "Beginner"
        else:
            difficulty = "Intermediate"

        # ── Determine confidence ──────────────────────────────────────────────
        critical_errors = {"repo_meta", "languages", "commits"}
        has_critical_errors = bool(critical_errors & set(m.fetch_errors))
        many_errors = len(m.fetch_errors) >= 3

        # Near a threshold (within 5 pts)
        near_threshold = (
            abs(complexity - 30) < 5    # near Beginner/Intermediate boundary
            or abs(complexity - 55) < 5  # near Intermediate/Advanced boundary (updated)
            or abs(activity - 45) < 5   # near contributor+activity Advanced trigger
        )

        if m.is_archived:
            confidence = "LOW"
        elif has_critical_errors or many_errors:
            confidence = "LOW"
        elif near_threshold or len(m.fetch_errors) > 0:
            confidence = "MEDIUM"
        else:
            confidence = "HIGH"

        return difficulty, confidence


# ── Observation Generator ─────────────────────────────────────────────────────

def generate_observations(m: RepoMetrics, activity: float, complexity: float,
                           activity_bd: ScoreBreakdown, difficulty: str) -> list[str]:
    """
    Auto-generate human-readable insights about each repository.
    """
    obs = []

    # Activity patterns
    if m.commits_30d == 0 and m.days_since_push > 90:
        obs.append(f"No commits in 90+ days — repo appears dormant (last push: {m.days_since_push} days ago).")
    elif m.commits_30d > 100:
        obs.append(f"Highly active: {m.commits_30d} commits in the last 30 days.")
    elif m.commits_30d > 20:
        obs.append(f"Consistently active with {m.commits_30d} commits in the last 30 days.")

    # Commit regularity insight
    reg_score = activity_bd.components.get("commit_regularity (20pts)", 0)
    if m.commits_30d > 5:
        if reg_score > 15:
            obs.append("Commit cadence is highly regular — sustained, consistent development pattern.")
        elif reg_score < 5:
            obs.append("Commits are bursty rather than regular — development happens in occasional sprints.")

    # Issue resolution
    if m.closed_issues_30d > 0 and m.open_issues > 0:
        ratio = m.closed_issues_30d / (m.closed_issues_30d + m.open_issues)
        if ratio > 0.7:
            obs.append(f"Excellent maintainer responsiveness: {ratio*100:.0f}% issue resolution rate.")
        elif ratio < 0.2:
            obs.append(f"Low issue resolution rate ({ratio*100:.0f}%) — issues accumulate faster than they're closed.")
    elif m.open_issues > 200:
        obs.append(f"Large open issue backlog ({m.open_issues} open issues) may indicate high demand or slow maintenance.")

    # Contributor dynamics
    if m.contributors_count == 1:
        obs.append("Solo maintainer project — no bus-factor resilience.")
    elif m.contributors_count <= 5:
        obs.append(f"Small team ({m.contributors_count} contributors) — intimate but potentially fragile.")
    elif m.contributors_count >= 500:
        obs.append(f"Massive contributor base ({m.contributors_count}) — one of the largest OSS communities; process complexity is significant.")
    elif m.contributors_count >= 100:
        obs.append(f"Large contributor base ({m.contributors_count}) — mature, community-driven project.")

    # Language complexity
    if len(m.languages) >= 5:
        lang_list = ", ".join(list(m.languages.keys())[:5])
        obs.append(f"Polyglot codebase ({len(m.languages)} languages: {lang_list}...) — requires broad technical knowledge.")
    elif len(m.languages) == 1:
        obs.append(f"Single-language codebase ({m.primary_language}) — easier to get started.")

    # Scale signals (new in v2)
    if m.file_count >= 50000:
        obs.append(f"Enormous codebase ({m.file_count:,} files) — navigating the source tree alone is a significant challenge.")
    elif m.file_count >= 10000:
        obs.append(f"Large codebase ({m.file_count:,} files) — significant investment needed to understand the architecture.")

    # Tech ecosystem breadth
    ecosystems = _detect_ecosystems(m.dependency_files)
    if len(ecosystems) >= 3:
        obs.append(f"Spans {len(ecosystems)} dependency ecosystems ({', '.join(ecosystems)}) — significant setup complexity.")

    # Systems build system detection (new in v2)
    systems_build = {"make", "cmake", "kbuild", "meson", "bazel"}
    detected_systems = systems_build & set(ecosystems)
    if detected_systems:
        obs.append(f"Uses systems-level build tooling ({', '.join(detected_systems)}) — requires familiarity beyond standard package managers.")

    # Difficulty-specific observations
    if difficulty == "Beginner":
        obs.append("Good first-contribution target: low complexity, small team, accessible codebase.")
    elif difficulty == "Advanced":
        obs.append("Requires deep technical background — not recommended as a first OSS contribution.")
    elif difficulty == "Intermediate":
        obs.append("Reasonable entry point for developers with some OSS experience.")
    elif difficulty == "Too New":
        obs.append("Repository is too new to classify reliably — revisit after at least 2 weeks of activity.")

    # Archived notice
    if m.is_archived:
        obs.append("⚠️  Repository is archived — read-only, no longer accepting contributions.")

    # Fork notice
    if m.is_fork:
        obs.append("This repository is a fork — activity and complexity reflect the fork, not the upstream.")

    # Data quality warnings
    if m.fetch_errors:
        obs.append(f"Note: Some data could not be fetched ({', '.join(m.fetch_errors)}) — scores may be understated.")

    if not obs:
        obs.append("No strong activity or complexity signals detected — repository appears stable and straightforward.")

    return obs


# ── Full pipeline for one repo ────────────────────────────────────────────────

def analyze(metrics: RepoMetrics) -> AnalysisResult:
    """Score and classify one RepoMetrics object. Returns a complete AnalysisResult."""
    result = AnalysisResult(metrics=metrics)

    if metrics.is_private_or_missing:
        result.error = "Repository not found or is private."
        result.difficulty = "Unknown"
        result.confidence = "LOW"
        return result

    activity_scorer = ActivityScorer()
    complexity_scorer = ComplexityScorer()
    classifier = DifficultyClassifier()

    result.activity_breakdown = activity_scorer.score(metrics)
    result.activity_score = result.activity_breakdown.total

    result.complexity_breakdown = complexity_scorer.score(metrics)
    result.complexity_score = result.complexity_breakdown.total

    result.difficulty, result.confidence = classifier.classify(
        result.activity_score, result.complexity_score, metrics
    )

    result.observations = generate_observations(
        metrics, result.activity_score, result.complexity_score,
        result.activity_breakdown, result.difficulty
    )

    return result
