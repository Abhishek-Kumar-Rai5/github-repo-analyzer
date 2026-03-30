"""
test_scoring.py — Unit tests for all scoring functions.

Tests cover:
  - Empty / zero-data repos
  - Boundary conditions near difficulty thresholds
  - Shannon entropy correctness
  - Commit regularity edge cases
  - Log scaling properties
  - Recency decay values
  - Difficulty classifier multi-dimensional logic
  - Age normalization
  - Confidence ratings
"""

import math
import pytest
from datetime import datetime, timezone, timedelta

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.models import RepoMetrics
from analyzer.scoring import (
    ActivityScorer, ComplexityScorer, DifficultyClassifier,
    _shannon_entropy, _log_scale, _linear_scale,
    _commit_regularity_score, _recency_decay, analyze,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_metrics(**kwargs) -> RepoMetrics:
    """Build a RepoMetrics with sensible defaults, overrideable via kwargs."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        owner="test", name="repo", url="https://github.com/test/repo",
        stars=100, forks=20, watchers=100,
        primary_language="Python",
        languages={"Python": 80000, "JavaScript": 10000},
        contributors_count=10,
        commits_30d=30,
        commit_dates_30d=[
            (now - timedelta(days=i)).isoformat() for i in range(1, 31)
        ],
        open_issues=5, closed_issues_30d=10, total_issues=15,
        open_prs=3, merged_prs_30d=8,
        file_count=150, repo_size_kb=2000,
        dependency_files=["requirements.txt", "package.json"],
        tech_ecosystems=["pip", "npm"],
        created_at=now - timedelta(days=365),
        pushed_at=now - timedelta(days=2),
        age_days=365, days_since_push=2,
        is_archived=False, is_fork=False,
        fetch_errors=[],
    )
    defaults.update(kwargs)
    return RepoMetrics(**defaults)


# ── Utility function tests ─────────────────────────────────────────────────────

class TestLogScale:
    def test_zero_returns_zero(self):
        assert _log_scale(0, 1000, 25) == 0.0

    def test_at_ceiling_returns_max(self):
        result = _log_scale(1000, 1000, 25)
        assert abs(result - 25.0) < 0.01

    def test_never_exceeds_max(self):
        assert _log_scale(999999, 1000, 25) <= 25.0

    def test_grows_logarithmically(self):
        """Score at 10x value should NOT be 10x the score (log scale)."""
        s1 = _log_scale(10, 10000, 25)
        s2 = _log_scale(100, 10000, 25)
        s3 = _log_scale(1000, 10000, 25)
        # Each 10x increase gives the same absolute gain (linear in log space)
        gap_1_to_2 = s2 - s1
        gap_2_to_3 = s3 - s2
        assert abs(gap_1_to_2 - gap_2_to_3) < 0.5  # roughly equal jumps


class TestShannonEntropy:
    def test_single_language_is_zero(self):
        """One language → maximum certainty → entropy = 0."""
        assert _shannon_entropy({"Python": 100000}) == 0.0

    def test_empty_is_zero(self):
        assert _shannon_entropy({}) == 0.0

    def test_two_equal_languages(self):
        """50/50 split → entropy = log2(2) = 1.0."""
        result = _shannon_entropy({"Python": 1000, "JavaScript": 1000})
        assert abs(result - 1.0) < 0.01

    def test_entropy_increases_with_diversity(self):
        """More languages spread more evenly → higher entropy."""
        mono = _shannon_entropy({"Python": 10000})
        dual = _shannon_entropy({"Python": 5000, "JS": 5000})
        triple = _shannon_entropy({"Python": 3333, "JS": 3333, "Go": 3334})
        assert mono < dual < triple

    def test_skewed_distribution_lower_than_equal(self):
        """90/10 split should have lower entropy than 50/50."""
        skewed = _shannon_entropy({"Python": 9000, "JS": 1000})
        equal = _shannon_entropy({"Python": 5000, "JS": 5000})
        assert skewed < equal


class TestRecencyDecay:
    def test_zero_days_is_one(self):
        assert abs(_recency_decay(0) - 1.0) < 0.01

    def test_45_days_is_half(self):
        """At 45 days: e^(-1) ≈ 0.368."""
        result = _recency_decay(45)
        assert abs(result - math.exp(-1)) < 0.01

    def test_180_days_is_near_zero(self):
        assert _recency_decay(180) < 0.05

    def test_strictly_decreasing(self):
        scores = [_recency_decay(d) for d in [0, 7, 30, 60, 90, 180]]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1]


class TestCommitRegularity:
    def test_no_commits_returns_zero(self):
        assert _commit_regularity_score([]) == 0.0

    def test_one_commit_returns_zero(self):
        assert _commit_regularity_score(["2026-01-01T00:00:00+00:00"]) == 0.0

    def test_perfectly_regular_scores_high(self):
        """Commits evenly spaced (every day) → high regularity."""
        now = datetime.now(timezone.utc)
        dates = [(now - timedelta(days=i)).isoformat() for i in range(1, 31)]
        score = _commit_regularity_score(dates, max_pts=20)
        assert score > 12  # Should be well above midpoint

    def test_burst_commits_scores_low(self):
        """All commits on same day → very bursty → low regularity."""
        now = datetime.now(timezone.utc)
        dates = [now.isoformat()] * 30  # all today
        score = _commit_regularity_score(dates, max_pts=20)
        assert score < 8  # Should be below midpoint


# ── ActivityScorer tests ──────────────────────────────────────────────────────

class TestActivityScorer:
    scorer = ActivityScorer()

    def test_empty_repo_scores_near_zero(self):
        m = make_metrics(
            commits_30d=0, commit_dates_30d=[],
            stars=0, forks=0, contributors_count=0,
            open_issues=0, closed_issues_30d=0,
            open_prs=0, merged_prs_30d=0,
            days_since_push=365,
        )
        bd = self.scorer.score(m)
        assert bd.total < 10

    def test_highly_active_repo_scores_high(self):
        now = datetime.now(timezone.utc)
        m = make_metrics(
            commits_30d=150,
            commit_dates_30d=[(now - timedelta(days=i % 30)).isoformat() for i in range(150)],
            stars=10000, forks=2000, contributors_count=200,
            open_issues=50, closed_issues_30d=80,
            open_prs=10, merged_prs_30d=40,
            days_since_push=0,
        )
        bd = self.scorer.score(m)
        assert bd.total > 60

    def test_recency_decay_applied(self):
        """Same repo, different push dates → recent should score higher."""
        m_recent = make_metrics(days_since_push=1)
        m_old = make_metrics(days_since_push=200)
        bd_recent = self.scorer.score(m_recent)
        bd_old = self.scorer.score(m_old)
        assert bd_recent.total > bd_old.total

    def test_breakdown_components_present(self):
        m = make_metrics()
        bd = self.scorer.score(m)
        assert "commit_volume (25pts)" in bd.components
        assert "commit_regularity (20pts)" in bd.components
        assert "issue_resolution_rate (20pts)" in bd.components
        assert "recency_decay_factor" in bd.components

    def test_score_never_exceeds_100(self):
        now = datetime.now(timezone.utc)
        m = make_metrics(
            commits_30d=10000, stars=1000000, forks=500000,
            contributors_count=10000, closed_issues_30d=10000,
            merged_prs_30d=10000, days_since_push=0,
            commit_dates_30d=[(now - timedelta(hours=i)).isoformat() for i in range(100)],
        )
        bd = self.scorer.score(m)
        assert bd.total <= 100.0

    def test_issue_resolution_neutral_when_no_issues(self):
        """If there are no issues at all, resolution shouldn't penalize."""
        m_no_issues = make_metrics(open_issues=0, closed_issues_30d=0)
        m_with_issues = make_metrics(open_issues=10, closed_issues_30d=20)
        bd_no = ActivityScorer().score(m_no_issues)
        bd_with = ActivityScorer().score(m_with_issues)
        # Both should be reasonable; no-issues should not be dramatically lower
        assert bd_no.total > 5


# ── ComplexityScorer tests ────────────────────────────────────────────────────

class TestComplexityScorer:
    scorer = ComplexityScorer()

    def test_empty_repo_scores_near_zero(self):
        m = make_metrics(
            languages={}, file_count=0, repo_size_kb=0,
            dependency_files=[], tech_ecosystems=[],
            age_days=30,
        )
        bd = self.scorer.score(m)
        assert bd.total < 15

    def test_complex_repo_scores_high(self):
        m = make_metrics(
            languages={
                "Python": 40000, "TypeScript": 30000, "Go": 20000,
                "Rust": 10000, "C": 5000, "Shell": 2000
            },
            file_count=5000, repo_size_kb=100000,
            dependency_files=["requirements.txt", "package.json", "Cargo.toml", "go.mod", "Makefile"],
            tech_ecosystems=["pip", "npm", "cargo", "go"],
            age_days=1000,
        )
        bd = self.scorer.score(m)
        assert bd.total > 55

    def test_mono_language_scores_low_entropy(self):
        mono = make_metrics(languages={"Python": 100000})
        poly = make_metrics(languages={"Python": 33333, "JS": 33333, "Go": 33334})
        bd_mono = self.scorer.score(mono)
        bd_poly = self.scorer.score(poly)
        assert bd_poly.total > bd_mono.total

    def test_age_normalization_works(self):
        """Same size, different age → younger repo scores higher on size metric."""
        young = make_metrics(repo_size_kb=50000, age_days=30)
        old = make_metrics(repo_size_kb=50000, age_days=3000)
        bd_young = self.scorer.score(young)
        bd_old = self.scorer.score(old)
        young_age_score = bd_young.components.get("age_normalized_size (15pts)", 0)
        old_age_score = bd_old.components.get("age_normalized_size (15pts)", 0)
        assert young_age_score > old_age_score

    def test_ecosystem_count_matters(self):
        """More distinct ecosystems → higher tech breadth score."""
        one = make_metrics(tech_ecosystems=["pip"])
        three = make_metrics(tech_ecosystems=["pip", "npm", "cargo"])
        bd_one = self.scorer.score(one)
        bd_three = self.scorer.score(three)
        assert bd_three.total > bd_one.total

    def test_score_never_exceeds_100(self):
        m = make_metrics(
            languages={f"lang{i}": 10000 for i in range(20)},
            file_count=999999, repo_size_kb=9999999,
            dependency_files=[f"file{i}" for i in range(20)],
            tech_ecosystems=["npm", "pip", "cargo", "go", "maven"],
            age_days=1,
        )
        bd = self.scorer.score(m)
        assert bd.total <= 100.0


# ── DifficultyClassifier tests ────────────────────────────────────────────────

class TestDifficultyClassifier:
    clf = DifficultyClassifier()

    def test_clearly_beginner(self):
        m = make_metrics(contributors_count=2, age_days=90)
        diff, conf = self.clf.classify(activity=20, complexity=15, m=m)
        assert diff == "Beginner"

    def test_clearly_advanced_by_complexity(self):
        m = make_metrics(contributors_count=5, age_days=500)
        diff, conf = self.clf.classify(activity=30, complexity=70, m=m)
        assert diff == "Advanced"

    def test_clearly_advanced_by_contributors(self):
        m = make_metrics(contributors_count=100, age_days=500)
        diff, conf = self.clf.classify(activity=60, complexity=40, m=m)
        assert diff == "Advanced"

    def test_intermediate_is_default(self):
        m = make_metrics(contributors_count=15, age_days=200)
        diff, conf = self.clf.classify(activity=45, complexity=40, m=m)
        assert diff == "Intermediate"

    def test_too_new_repo(self):
        """Brand new repo (≤14 days) should not be classified."""
        m = make_metrics(age_days=5)
        diff, conf = self.clf.classify(activity=50, complexity=50, m=m)
        assert diff == "Too New"

    def test_archived_repo_is_low_confidence(self):
        m = make_metrics(is_archived=True)
        _, conf = self.clf.classify(activity=50, complexity=50, m=m)
        assert conf == "LOW"

    def test_many_fetch_errors_reduce_confidence(self):
        m = make_metrics(fetch_errors=["commits", "issues", "prs"])
        _, conf = self.clf.classify(activity=50, complexity=50, m=m)
        assert conf in ("LOW", "MEDIUM")

    def test_near_threshold_is_medium_confidence(self):
        """Complexity near 25 (Beginner/Intermediate boundary) → MEDIUM confidence."""
        m = make_metrics(contributors_count=15, age_days=200, fetch_errors=[])
        _, conf = self.clf.classify(activity=50, complexity=27, m=m)
        assert conf == "MEDIUM"

    def test_high_confidence_clean_data(self):
        m = make_metrics(contributors_count=50, age_days=500, fetch_errors=[])
        diff, conf = self.clf.classify(activity=80, complexity=80, m=m)
        assert conf == "HIGH"


# ── Full pipeline analyze() tests ─────────────────────────────────────────────

class TestAnalyze:
    def test_missing_repo_returns_error(self):
        m = RepoMetrics(owner="x", name="y", is_private_or_missing=True)
        result = analyze(m)
        assert result.error is not None
        assert result.difficulty == "Unknown"

    def test_normal_repo_has_all_fields(self):
        m = make_metrics()
        result = analyze(m)
        assert result.activity_score >= 0
        assert result.complexity_score >= 0
        assert result.difficulty in ("Beginner", "Intermediate", "Advanced", "Too New")
        assert result.confidence in ("HIGH", "MEDIUM", "LOW")
        assert isinstance(result.observations, list)
        assert len(result.observations) > 0

    def test_archived_repo_observation_present(self):
        m = make_metrics(is_archived=True)
        result = analyze(m)
        obs_text = " ".join(result.observations)
        assert "archived" in obs_text.lower()

    def test_solo_maintainer_observation(self):
        m = make_metrics(contributors_count=1)
        result = analyze(m)
        obs_text = " ".join(result.observations)
        assert "solo" in obs_text.lower() or "maintainer" in obs_text.lower()

    def test_dormant_repo_observation(self):
        m = make_metrics(commits_30d=0, days_since_push=120)
        result = analyze(m)
        obs_text = " ".join(result.observations)
        assert "dormant" in obs_text.lower() or "no commits" in obs_text.lower()


# ── Edge case integration tests ───────────────────────────────────────────────

class TestEdgeCases:
    def test_zero_age_days_no_crash(self):
        """age_days=0 should not cause division by zero."""
        m = make_metrics(age_days=0)
        result = analyze(m)
        assert result is not None

    def test_huge_values_no_crash(self):
        """Extremely large values should not overflow or crash."""
        m = make_metrics(
            stars=10**9, forks=10**8, commits_30d=10**6,
            file_count=10**7, repo_size_kb=10**9,
        )
        result = analyze(m)
        assert result.activity_score <= 100.0
        assert result.complexity_score <= 100.0

    def test_all_fetch_errors_low_confidence(self):
        m = make_metrics(fetch_errors=["repo_meta", "languages", "commits", "issues", "prs"])
        result = analyze(m)
        assert result.confidence == "LOW"

    def test_fork_observation_present(self):
        m = make_metrics(is_fork=True)
        result = analyze(m)
        obs_text = " ".join(result.observations)
        assert "fork" in obs_text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
