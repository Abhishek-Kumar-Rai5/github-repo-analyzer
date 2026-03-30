"""
models.py — Single source of truth for all data structures.
Every module imports from here. No raw dicts passed around.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RepoMetrics:
    """Raw data fetched from GitHub API for one repository."""

    # Identity
    owner: str = ""
    name: str = ""
    url: str = ""
    description: str = ""

    # Popularity
    stars: int = 0
    forks: int = 0
    watchers: int = 0

    # Language
    primary_language: str = ""
    languages: dict = field(default_factory=dict)   # {"Python": 85432, "JS": 12000}

    # People
    contributors_count: int = 0

    # Commit activity
    commits_30d: int = 0
    commits_total: int = 0
    commit_dates_30d: list = field(default_factory=list)  # ISO strings for regularity calc

    # Issues
    open_issues: int = 0
    closed_issues_30d: int = 0
    total_issues: int = 0

    # Pull requests
    open_prs: int = 0
    merged_prs_30d: int = 0

    # Codebase structure
    file_count: int = 0
    repo_size_kb: int = 0
    dependency_files: list = field(default_factory=list)  # ["package.json", "requirements.txt"]
    tech_ecosystems: list = field(default_factory=list)   # ["npm", "pip", "cargo"]

    # Timestamps
    created_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None
    age_days: int = 0
    days_since_push: int = 0

    # Metadata
    is_archived: bool = False
    is_fork: bool = False
    has_wiki: bool = False
    license: str = ""
    topics: list = field(default_factory=list)

    # Data quality tracking
    fetch_errors: list = field(default_factory=list)   # list of field names that failed
    is_private_or_missing: bool = False

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class ScoreBreakdown:
    """Sub-scores for one dimension (activity or complexity)."""
    total: float = 0.0
    components: dict = field(default_factory=dict)  # component_name → score


@dataclass
class AnalysisResult:
    """Full analysis output for one repository."""
    metrics: RepoMetrics = field(default_factory=RepoMetrics)
    activity_score: float = 0.0
    activity_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    complexity_score: float = 0.0
    complexity_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    difficulty: str = "Unknown"
    confidence: str = "HIGH"   # HIGH / MEDIUM / LOW
    observations: list = field(default_factory=list)
    error: Optional[str] = None  # set if repo could not be analyzed at all
