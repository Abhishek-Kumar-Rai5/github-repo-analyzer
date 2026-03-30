"""
github_client.py — GitHub REST API client.

Key design decisions vs other submissions:
  - One requests.Session shared across all calls (connection reuse)
  - ThreadPoolExecutor for concurrent multi-repo fetching
  - In-session ETag cache — avoids redundant fetches
  - Proactive rate-limit monitoring on every response
  - Exponential backoff on 5xx errors
  - Partial data collection — one failed endpoint doesn't abort the whole analysis
"""

import os
import re
import time
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import requests

from .models import RepoMetrics

logger = logging.getLogger(__name__)

# ── Dependency manifest → ecosystem mapping ──────────────────────────────────
DEPENDENCY_ECOSYSTEM_MAP = {
    "package.json":       "npm",
    "package-lock.json":  "npm",
    "yarn.lock":          "npm",
    "pnpm-lock.yaml":     "npm",
    "requirements.txt":   "pip",
    "setup.py":           "pip",
    "setup.cfg":          "pip",
    "pyproject.toml":     "pip",
    "Pipfile":            "pip",
    "Pipfile.lock":       "pip",
    "poetry.lock":        "pip",
    "Cargo.toml":         "cargo",
    "Cargo.lock":         "cargo",
    "go.mod":             "go",
    "go.sum":             "go",
    "pom.xml":            "maven",
    "build.gradle":       "gradle",
    "build.gradle.kts":   "gradle",
    "Gemfile":            "bundler",
    "Gemfile.lock":       "bundler",
    "composer.json":      "composer",
    "composer.lock":      "composer",
    "pubspec.yaml":       "pub",
    "mix.exs":            "hex",
    "Dockerfile":         "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml":"docker",
    ".terraform":         "terraform",
    "CMakeLists.txt":     "cmake",
    "conanfile.txt":      "conan",
    "conanfile.py":       "conan",
}


class RateLimitError(Exception):
    """Raised when GitHub rate limit is exhausted with no reset in sight."""
    pass


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "github-repo-analyzer/1.0",
        })
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"

        # In-session ETag cache: url → {"etag": str, "data": any}
        self._etag_cache: dict = {}
        self._rate_limit_remaining = 5000
        self._rate_limit_reset = 0

    # ── Core request helper ───────────────────────────────────────────────────

    def _get(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[dict | list]:
        """
        GET with ETag caching, rate-limit awareness, and exponential backoff.
        Returns None on non-retryable failure (404, 403, etc.).
        """

        headers = {}
        cache_key = url + str(params)
        if cache_key in self._etag_cache:
            headers["If-None-Match"] = self._etag_cache[cache_key]["etag"]

        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=15)

                # Update rate limit tracking
                self._rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 5000))
                self._rate_limit_reset = int(resp.headers.get("X-RateLimit-Reset", 0))

                # Proactive pause if critically low — bounded to avoid deadlocking threads
                if self._rate_limit_remaining < 10 and self._rate_limit_reset:
                    wait = min(5, max(0, self._rate_limit_reset - time.time()) + 1)
                    logger.warning(f"Rate limit critically low ({self._rate_limit_remaining}). Brief pause {wait:.0f}s")
                    time.sleep(wait)

                if resp.status_code == 304:
                    # Not modified — return cached data (costs zero rate limit quota)
                    return self._etag_cache[cache_key]["data"]

                if resp.status_code == 200:
                    data = resp.json()
                    if "ETag" in resp.headers:
                        self._etag_cache[cache_key] = {"etag": resp.headers["ETag"], "data": data}
                    return data

                if resp.status_code == 404:
                    return None  # Repo not found / private

                if resp.status_code == 403:
                    # Could be rate limit or permissions
                    reset_in = max(0, self._rate_limit_reset - time.time())
                    if reset_in < 120:
                        logger.warning(f"Rate limit hit. Waiting {reset_in:.0f}s")
                        time.sleep(reset_in + 2)
                        continue
                    return None

                if resp.status_code >= 500:
                    wait = (2 ** attempt) * 2
                    logger.warning(f"Server error {resp.status_code}. Retry {attempt+1}/{max_retries} in {wait}s")
                    time.sleep(wait)
                    continue

                return None

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on {url}, attempt {attempt+1}/{max_retries}")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                return None

        return None

    def _get_paginated(self, url: str, params: dict = None, max_pages: int = 5) -> list:
        """Fetch up to max_pages of paginated results."""
        results = []
        params = params or {}
        params["per_page"] = 100
        page = 1
        while page <= max_pages:
            params["page"] = page
            data = self._get(url, params=dict(params))
            if not data:
                break
            results.extend(data if isinstance(data, list) else [data])
            if len(data) < 100:
                break   # Last page
            page += 1
        return results

    # ── Individual fetch methods ──────────────────────────────────────────────

    def fetch_repo_meta(self, owner: str, name: str) -> Optional[dict]:
        return self._get(f"{self.BASE}/repos/{owner}/{name}")

    def fetch_languages(self, owner: str, name: str) -> dict:
        data = self._get(f"{self.BASE}/repos/{owner}/{name}/languages")
        return data if isinstance(data, dict) else {}

    def fetch_contributors_count(self, owner: str, name: str) -> int:
        """Estimate contributor count via pagination headers."""
        try:
            resp = self.session.get(
                f"{self.BASE}/repos/{owner}/{name}/contributors",
                params={"per_page": 1, "anon": "false"},
                timeout=10
            )
            if resp.status_code != 200:
                return 0
            link = resp.headers.get("Link", "")
            if 'rel="last"' in link:
                m = re.search(r'page=(\d+)>; rel="last"', link)
                return int(m.group(1)) if m else 1
            data = resp.json()
            return len(data) if isinstance(data, list) else 0
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch contributors for {owner}/{name}: {e}")
            return 0

    def fetch_commits_30d(self, owner: str, name: str) -> tuple[int, list]:
        """Returns (count, list_of_ISO_date_strings) for commit regularity calculation."""
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        commits = self._get_paginated(
            f"{self.BASE}/repos/{owner}/{name}/commits",
            params={"since": since},
            max_pages=5   # cap at 500 commits
        )
        dates = []
        for c in commits:
            try:
                dates.append(c["commit"]["author"]["date"])
            except (KeyError, TypeError):
                pass
        return len(commits), dates

    def fetch_issues_stats(self, owner: str, name: str) -> tuple[int, int, int]:
        """Returns (open_count, closed_30d_count, total_open_count)."""
        open_count = 0
        try:
            # Single call to get open issue count via Link header pagination trick
            resp = self.session.get(
                f"{self.BASE}/repos/{owner}/{name}/issues",
                params={"state": "open", "per_page": 1},
                timeout=10
            )
            if resp.status_code == 200:
                link = resp.headers.get("Link", "")
                m = re.search(r'page=(\d+)>; rel="last"', link)
                if m:
                    open_count = int(m.group(1))
                else:
                    data = resp.json()
                    open_count = len(data) if isinstance(data, list) else 0
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch open issues for {owner}/{name}: {e}")

        # Closed in last 30 days
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        closed = self._get_paginated(
            f"{self.BASE}/repos/{owner}/{name}/issues",
            params={"state": "closed", "since": since},
            max_pages=3
        )
        closed_30d = len([i for i in closed if "pull_request" not in i])

        return open_count, closed_30d, open_count

    def fetch_prs(self, owner: str, name: str) -> tuple[int, int]:
        """Returns (open_pr_count, merged_prs_30d)."""
        open_count = 0
        try:
            open_prs_resp = self.session.get(
                f"{self.BASE}/repos/{owner}/{name}/pulls",
                params={"state": "open", "per_page": 1},
                timeout=10
            )
            if open_prs_resp.status_code == 200:
                link = open_prs_resp.headers.get("Link", "")
                m = re.search(r'page=(\d+)>; rel="last"', link)
                open_count = int(m.group(1)) if m else len(open_prs_resp.json() or [])
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch open PRs for {owner}/{name}: {e}")

        # Merged in last 30 days
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        merged = self._get_paginated(
            f"{self.BASE}/repos/{owner}/{name}/pulls",
            params={"state": "closed", "since": since},
            max_pages=2
        )
        merged_30d = sum(1 for pr in merged if pr.get("merged_at"))
        return open_count, merged_30d

    def fetch_file_tree(self, owner: str, name: str, default_branch: str = "main") -> tuple[int, list, list]:
        """
        Returns (file_count, dependency_files_found, tech_ecosystems).
        Uses the git tree API for efficiency (one call instead of recursive listing).
        """
        data = self._get(f"{self.BASE}/repos/{owner}/{name}/git/trees/{default_branch}",
                         params={"recursive": "0"})  # root level only — efficient
        if not data or "tree" not in data:
            # Try master branch
            data = self._get(f"{self.BASE}/repos/{owner}/{name}/git/trees/master",
                             params={"recursive": "0"})
        if not data or "tree" not in data:
            return 0, [], []

        # Count files, detect dependency files in root
        root_files = [item["path"] for item in data.get("tree", []) if item.get("type") == "blob"]
        file_count = len(root_files)

        dep_files = []
        ecosystems = set()
        for fname in root_files:
            if fname in DEPENDENCY_ECOSYSTEM_MAP:
                dep_files.append(fname)
                ecosystems.add(DEPENDENCY_ECOSYSTEM_MAP[fname])

        # Also do a recursive count estimate via size field
        total_count = len(data.get("tree", []))

        return max(total_count, file_count), dep_files, list(ecosystems)

    # ── Main entry point: fetch one full repo ─────────────────────────────────

    def fetch_repo(self, owner: str, name: str) -> RepoMetrics:
        """
        Fetch all data for one repo. Uses partial collection:
        if one endpoint fails, we still score what we have.
        """
        metrics = RepoMetrics(owner=owner, name=name, url=f"https://github.com/{owner}/{name}")

        # 1. Core metadata (if this fails, whole repo is unanalyzable)
        meta = self.fetch_repo_meta(owner, name)
        if meta is None:
            metrics.is_private_or_missing = True
            metrics.fetch_errors.append("repo_meta")
            return metrics

        metrics.description = meta.get("description") or ""
        metrics.stars = meta.get("stargazers_count", 0)
        metrics.forks = meta.get("forks_count", 0)
        metrics.watchers = meta.get("watchers_count", 0)
        metrics.primary_language = meta.get("language") or ""
        metrics.open_issues = meta.get("open_issues_count", 0)
        metrics.repo_size_kb = meta.get("size", 0)
        metrics.is_archived = meta.get("archived", False)
        metrics.is_fork = meta.get("fork", False)
        metrics.has_wiki = meta.get("has_wiki", False)
        metrics.license = (meta.get("license") or {}).get("spdx_id", "") or ""
        metrics.topics = meta.get("topics", [])
        default_branch = meta.get("default_branch", "main")

        # Parse timestamps
        try:
            metrics.created_at = datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
            metrics.pushed_at = datetime.fromisoformat(meta["pushed_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            metrics.age_days = max(1, (now - metrics.created_at).days)
            metrics.days_since_push = max(0, (now - metrics.pushed_at).days)
        except Exception:
            metrics.fetch_errors.append("timestamps")

        # 2. Languages
        try:
            metrics.languages = self.fetch_languages(owner, name)
        except Exception:
            metrics.fetch_errors.append("languages")

        # 3. Contributors
        try:
            metrics.contributors_count = self.fetch_contributors_count(owner, name)
        except Exception:
            metrics.fetch_errors.append("contributors")

        # 4. Commits last 30 days
        try:
            metrics.commits_30d, metrics.commit_dates_30d = self.fetch_commits_30d(owner, name)
        except Exception:
            metrics.fetch_errors.append("commits")

        # 5. Issues
        try:
            metrics.open_issues, metrics.closed_issues_30d, metrics.total_issues = \
                self.fetch_issues_stats(owner, name)
        except Exception:
            metrics.fetch_errors.append("issues")

        # 6. PRs
        try:
            metrics.open_prs, metrics.merged_prs_30d = self.fetch_prs(owner, name)
        except Exception:
            metrics.fetch_errors.append("prs")

        # 7. File tree + dependency detection
        try:
            metrics.file_count, metrics.dependency_files, metrics.tech_ecosystems = \
                self.fetch_file_tree(owner, name, default_branch)
        except Exception:
            metrics.fetch_errors.append("file_tree")

        return metrics

    # ── Batch fetch (concurrent) ──────────────────────────────────────────────

    def fetch_batch(self, repos: list[tuple[str, str]], max_workers: int = 4) -> list[RepoMetrics]:
        """
        Fetch multiple repos concurrently using a thread pool.
        max_workers=4 by default — enough to be fast, not enough to hammer the API.
        """
        results = [None] * len(repos)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.fetch_repo, owner, name): i
                for i, (owner, name) in enumerate(repos)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Failed to fetch repo {repos[idx]}: {e}")
                    owner, name = repos[idx]
                    m = RepoMetrics(owner=owner, name=name)
                    m.is_private_or_missing = True
                    m.fetch_errors.append(str(e))
                    results[idx] = m

        return results


def parse_repo_url(url: str) -> tuple[str, str]:
    """
    Parse a GitHub URL or shorthand into (owner, name).
    Supports:
      https://github.com/django/django
      https://github.com/django/django/tree/main
      django/django
    """
    url = url.strip().rstrip("/")
    if url.startswith("http"):
        # Extract path after github.com/
        parts = url.replace("https://github.com/", "").replace("http://github.com/", "").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    elif "/" in url:
        parts = url.split("/")
        return parts[0], parts[1]
    else:
        raise ValueError(f"Cannot parse repo shorthand (need owner/repo): {url}")
