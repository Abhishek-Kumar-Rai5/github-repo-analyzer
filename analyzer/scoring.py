"""
scoring.py — Activity Score, Complexity Score, and Difficulty Classifier.

Design philosophy:
  - Every formula component is independently testable
  - Log scaling handles the enormous variance between repos (1 star vs 100k stars)
  - Shannon entropy for language distribution (smarter than raw language count)
  - Commit cadence regularity (not just volume)
  - Issue resolution rate as maintainer responsiveness proxy
  - Age normalization: new repos aren't penalized unfairly
  - Multi-dimensional difficulty classifier with confidence rating

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
        # 0 or 1 commit: no regularity to measure
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

    # Coefficient of variation: std/mean — lower = more regular
    mean = statistics.mean(days)
    std = statistics.stdev(days)
    if mean == 0:
        # All commits on the same day — no spread to measure regularity from
        return max_pts * 0.3  # Partial credit only
    cv = std / mean

    # CV of 0 = perfectly regular = full score
    # CV of 2+ = very bursty = near-zero score
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


# ── Activity Scorer ───────────────────────────────────────────────────────────

class ActivityScorer:
    """
    Measures how alive and actively maintained a repository is right now.

    Score components (total = 100 pts before decay):
      commit_volume     25 pts  — raw commits in last 30 days (log scaled)
      commit_regularity 20 pts  — how evenly commits are spread (unique signal)
      issue_resolution  20 pts  — closed/(closed+open) ratio = maintainer responsiveness
      pr_merge_rate     15 pts  — PRs actually getting merged = code moving forward
      contributor_health 10 pts — team size (log scaled)
      community_signal  10 pts  — stars + forks (log scaled, weak signal)

    Final score: weighted_sum × recency_decay(days_since_push)
    This means a dormant repo cannot score high even with great historical metrics.
    """

    def score(self, m: RepoMetrics) -> ScoreBreakdown:
        bd = ScoreBreakdown()

        # 1. Commit volume (25 pts) — log scaled, ceiling at 200 commits/30d
        commit_vol = _log_scale(m.commits_30d, 200, 25.0)

        # 2. Commit regularity (20 pts) — unique: measures cadence, not just volume
        commit_reg = _commit_regularity_score(m.commit_dates_30d, 20.0)
        # If no commits, no regularity
        if m.commits_30d == 0:
            commit_reg = 0.0

        # 3. Issue resolution rate (20 pts)
        # Ratio: closed_30d / (closed_30d + open_issues)
        # A repo that closes issues quickly is actively maintained
        total_issue_activity = m.closed_issues_30d + max(m.open_issues, 0)
        if total_issue_activity > 0:
            resolution_ratio = m.closed_issues_30d / total_issue_activity
        else:
            # No issue activity at all — neutral (not penalized, not rewarded)
            resolution_ratio = 0.5
        issue_res = resolution_ratio * 20.0

        # 4. PR merge rate (15 pts)
        # merged_prs_30d / max(open_prs, 1) — how quickly PRs land
        if m.open_prs + m.merged_prs_30d > 0:
            pr_ratio = m.merged_prs_30d / (m.merged_prs_30d + max(m.open_prs, 1))
        else:
            pr_ratio = 0.0
        # Also reward sheer volume of merges (log scaled)
        pr_volume = _log_scale(m.merged_prs_30d, 50, 7.5)
        pr_score = (pr_ratio * 7.5) + pr_volume

        # 5. Contributor health (10 pts) — log scaled, ceiling at 500
        contributor_score = _log_scale(m.contributors_count, 500, 10.0)

        # 6. Community signal (10 pts) — log scaled stars + forks
        # Stars ceiling at 50,000 (beyond that, it's more fame than activity)
        stars_score = _log_scale(m.stars, 50000, 6.0)
        forks_score = _log_scale(m.forks, 10000, 4.0)
        community = stars_score + forks_score

        raw_total = commit_vol + commit_reg + issue_res + pr_score + contributor_score + community

        # Apply recency decay — dormant repos cannot score high
        decay = _recency_decay(m.days_since_push)
        final = min(100.0, raw_total * decay)

        bd.components = {
            "commit_volume (25pts)": round(commit_vol, 2),
            "commit_regularity (20pts)": round(commit_reg, 2),
            "issue_resolution_rate (20pts)": round(issue_res, 2),
            "pr_merge_rate (15pts)": round(pr_score, 2),
            "contributor_health (10pts)": round(contributor_score, 2),
            "community_signal (10pts)": round(community, 2),
            "recency_decay_factor": round(decay, 3),
            "raw_before_decay": round(raw_total, 2),
        }
        bd.total = round(final, 2)
        return bd


# ── Complexity Scorer ─────────────────────────────────────────────────────────

class ComplexityScorer:
    """
    Measures how structurally complex a codebase is to understand and contribute to.

    Score components (total = 100 pts):
      language_entropy   30 pts  — Shannon entropy of language distribution
      tech_breadth       25 pts  — number of distinct dependency ecosystems (npm, pip, cargo...)
      codebase_depth     20 pts  — log-scaled file count
      age_normalized_size 15 pts — repo_size_kb / age_days (avoids penalizing old repos)
      dependency_surface 10 pts  — count of distinct manifest files

    Why Shannon entropy instead of raw language count?
      See _shannon_entropy() docstring above. Raw count is a poor proxy.

    Why age-normalized size?
      A 5-year-old repo with 50MB is normal. A 1-month-old repo with 50MB is unusual.
      Age normalization catches genuinely large-for-their-age repos.
    """

    # Maximum expected entropy for normalization (~log2(10 languages) = 3.32)
    MAX_ENTROPY = math.log2(10)

    def score(self, m: RepoMetrics) -> ScoreBreakdown:
        bd = ScoreBreakdown()

        # 1. Language entropy (30 pts)
        entropy = _shannon_entropy(m.languages)
        lang_score = min(entropy / self.MAX_ENTROPY, 1.0) * 30.0
        # Bonus for simply having languages at all (mono-language repos still start at 0)
        if not m.languages and m.primary_language:
            lang_score = 5.0  # Single language, at least confirmed

        # 2. Tech breadth — distinct ecosystems (25 pts)
        # npm + pip + cargo = 3 ecosystems = genuinely complex
        # Just package.json + package-lock.json = 1 ecosystem (npm)
        ecosystem_count = len(set(m.tech_ecosystems))
        tech_score = _linear_scale(ecosystem_count, 5, 25.0)

        # 3. Codebase depth — file count (20 pts)
        # Log scaled, ceiling at 10,000 files
        depth_score = _log_scale(m.file_count, 10000, 20.0)

        # 4. Age-normalized size (15 pts)
        # size_per_day = repo_size_kb / age_days
        # Ceiling at 100 KB/day (tensorflow = ~6,000 KB/day = max)
        if m.age_days > 0:
            size_per_day = m.repo_size_kb / m.age_days
        else:
            size_per_day = 0
        age_size_score = _log_scale(size_per_day, 100, 15.0)

        # 5. Dependency surface (10 pts)
        # Raw count of distinct manifest files found in root
        dep_count = len(m.dependency_files)
        dep_score = _linear_scale(dep_count, 8, 10.0)

        total = lang_score + tech_score + depth_score + age_size_score + dep_score

        bd.components = {
            "language_entropy (30pts)": round(lang_score, 2),
            "tech_ecosystem_breadth (25pts)": round(tech_score, 2),
            "codebase_depth_files (20pts)": round(depth_score, 2),
            "age_normalized_size (15pts)": round(age_size_score, 2),
            "dependency_surface (10pts)": round(dep_score, 2),
            "raw_entropy_value": round(entropy, 4),
            "ecosystem_count": ecosystem_count,
        }
        bd.total = round(min(100.0, total), 2)
        return bd


# ── Difficulty Classifier ─────────────────────────────────────────────────────

class DifficultyClassifier:
    """
    Multi-dimensional classification — NOT a simple combined score threshold.

    Why not a simple threshold?
      Everyone else does: combined = activity*0.4 + complexity*0.6; if < 30 → Beginner.
      This produces absurd results: a dormant, zero-complexity repo with 10k stars
      might score "Intermediate" purely on activity from old data.

    Our decision tree:
      BEGINNER:      complexity < 25 AND contributors ≤ 8 AND age > 14 days
      ADVANCED:      complexity ≥ 65 OR (contributors ≥ 50 AND activity ≥ 55)
      INTERMEDIATE:  everything else

    Confidence rating:
      HIGH:   all key metrics available, scores far from thresholds
      MEDIUM: some fetch errors OR scores within 5 pts of a threshold
      LOW:    many fetch errors OR repo is archived/missing data
    """

    def classify(self, activity: float, complexity: float, m: RepoMetrics) -> tuple[str, str]:
        """Returns (difficulty_label, confidence_level)."""

        # ── Determine difficulty ──────────────────────────────────────────────
        is_beginner = (
            complexity < 25
            and m.contributors_count <= 8
            and m.age_days > 14        # brand new repos get no classification
        )

        is_advanced = (
            complexity >= 65
            or (m.contributors_count >= 50 and activity >= 55)
            or (complexity >= 50 and m.contributors_count >= 100)
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
            abs(complexity - 25) < 5   # near Beginner/Intermediate boundary
            or abs(complexity - 65) < 5  # near Intermediate/Advanced boundary
            or abs(activity - 55) < 5
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
    This is what makes reports feel intelligent rather than just numerical.
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
    elif m.contributors_count >= 100:
        obs.append(f"Large contributor base ({m.contributors_count}) — mature, community-driven project.")

    # Language complexity
    if len(m.languages) >= 5:
        lang_list = ", ".join(list(m.languages.keys())[:5])
        obs.append(f"Polyglot codebase ({len(m.languages)} languages: {lang_list}...) — requires broad technical knowledge.")
    elif len(m.languages) == 1:
        obs.append(f"Single-language codebase ({m.primary_language}) — easier to get started.")

    # Tech ecosystem breadth
    if len(m.tech_ecosystems) >= 3:
        obs.append(f"Spans {len(m.tech_ecosystems)} dependency ecosystems ({', '.join(m.tech_ecosystems)}) — significant setup complexity.")

    # Difficulty-specific observations
    if difficulty == "Beginner":
        obs.append("Good first-contribution target: low complexity, small team, accessible codebase.")
    elif difficulty == "Advanced":
        obs.append("Requires deep technical background — not recommended as a first OSS contribution.")
    elif difficulty == "Intermediate":
        obs.append("Reasonable entry point for developers with some OSS experience.")

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
