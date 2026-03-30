"""
test_pipeline.py — Tests for URL parsing and pipeline orchestration.
Uses mocking to avoid real GitHub API calls.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.github_client import parse_repo_url
from analyzer.models import RepoMetrics, AnalysisResult
from analyzer.scoring import analyze


class TestParseRepoUrl:
    def test_full_https_url(self):
        owner, name = parse_repo_url("https://github.com/django/django")
        assert owner == "django"
        assert name == "django"

    def test_https_url_with_trailing_slash(self):
        owner, name = parse_repo_url("https://github.com/django/django/")
        assert owner == "django"
        assert name == "django"

    def test_https_url_with_tree_path(self):
        owner, name = parse_repo_url("https://github.com/django/django/tree/main")
        assert owner == "django"
        assert name == "django"

    def test_owner_slash_name_shorthand(self):
        owner, name = parse_repo_url("django/django")
        assert owner == "django"
        assert name == "django"

    def test_whitespace_stripped(self):
        owner, name = parse_repo_url("  django/django  ")
        assert owner == "django"
        assert name == "django"

    def test_invalid_no_slash_raises(self):
        with pytest.raises(ValueError):
            parse_repo_url("justareponame")

    def test_invalid_empty_raises(self):
        with pytest.raises(ValueError):
            parse_repo_url("")

    def test_org_with_hyphen(self):
        owner, name = parse_repo_url("my-org/my-repo")
        assert owner == "my-org"
        assert name == "my-repo"


class TestAnalyzeMissingRepo:
    def test_private_or_missing(self):
        m = RepoMetrics(owner="nobody", name="nonexistent", is_private_or_missing=True)
        result = analyze(m)
        assert result.error is not None
        assert result.difficulty == "Unknown"
        assert result.confidence == "LOW"

    def test_error_result_has_metrics(self):
        m = RepoMetrics(owner="nobody", name="nonexistent", is_private_or_missing=True)
        result = analyze(m)
        assert result.metrics is not None
        assert result.metrics.owner == "nobody"


class TestAnalyzePartialData:
    """Test that partial data (some fetch errors) still produces a result."""

    def test_missing_commits_still_scores(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        m = RepoMetrics(
            owner="test", name="repo",
            stars=500, forks=50,
            contributors_count=20,
            commits_30d=0,       # No commit data
            commit_dates_30d=[],
            open_issues=10, closed_issues_30d=5,
            open_prs=2, merged_prs_30d=3,
            file_count=200, repo_size_kb=3000,
            languages={"Python": 80000},
            dependency_files=["requirements.txt"],
            tech_ecosystems=["pip"],
            created_at=now - timedelta(days=300),
            pushed_at=now - timedelta(days=5),
            age_days=300, days_since_push=5,
            fetch_errors=["commits"],
        )
        result = analyze(m)
        assert result.activity_score >= 0
        assert result.difficulty != "Unknown"
        assert "commits" in " ".join(result.observations) or result.confidence in ("MEDIUM", "LOW")

    def test_missing_languages_still_scores(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        m = RepoMetrics(
            owner="test", name="repo",
            stars=100, forks=10,
            contributors_count=5,
            commits_30d=20,
            commit_dates_30d=[(now - timedelta(days=i)).isoformat() for i in range(1, 21)],
            open_issues=3, closed_issues_30d=7,
            open_prs=1, merged_prs_30d=2,
            file_count=80, repo_size_kb=500,
            languages={},        # No language data
            dependency_files=[],
            tech_ecosystems=[],
            created_at=now - timedelta(days=180),
            pushed_at=now - timedelta(days=1),
            age_days=180, days_since_push=1,
            fetch_errors=["languages"],
        )
        result = analyze(m)
        assert result.complexity_score >= 0
        assert result.difficulty != "Unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
