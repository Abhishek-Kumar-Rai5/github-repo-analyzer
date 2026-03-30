"""
pipeline.py — Orchestrates the full analysis flow.

Takes a list of raw URL strings → validates → fetches concurrently
→ scores → returns list of AnalysisResult.
"""

import logging
from typing import Optional
from .github_client import GitHubClient, parse_repo_url
from .scoring import analyze
from .models import AnalysisResult, RepoMetrics

logger = logging.getLogger(__name__)


def run_analysis(
    repo_urls: list[str],
    token: Optional[str] = None,
    max_workers: int = 4,
    progress_callback=None,   # optional callable(current, total, repo_name)
) -> list[AnalysisResult]:
    """
    Main entry point. Given a list of GitHub repo URLs:
      1. Parse and validate all URLs
      2. Fetch all repos concurrently
      3. Score each repo
      4. Return ordered list of AnalysisResult (same order as input)

    Args:
        repo_urls:        List of GitHub URLs or owner/repo shorthands
        token:            GitHub Personal Access Token (optional but recommended)
        max_workers:      Concurrent fetch threads (default 4)
        progress_callback: Called after each repo is scored

    Returns:
        List of AnalysisResult, one per input URL (errors included, not raised)
    """
    client = GitHubClient(token=token)
    results = []

    # ── Step 1: Parse URLs ────────────────────────────────────────────────────
    parsed = []
    parse_errors = []

    for url in repo_urls:
        url = url.strip()
        if not url:
            continue
        try:
            owner, name = parse_repo_url(url)
            parsed.append((owner, name, url))
        except ValueError as e:
            r = AnalysisResult()
            r.error = str(e)
            r.metrics = RepoMetrics(url=url)
            r.difficulty = "Unknown"
            r.confidence = "LOW"
            parse_errors.append((url, r))
            logger.warning(f"Could not parse URL: {url} — {e}")

    if not parsed:
        return [e for _, e in parse_errors]

    # ── Step 2: Fetch concurrently ────────────────────────────────────────────
    repo_pairs = [(owner, name) for owner, name, _ in parsed]
    logger.info(f"Fetching {len(repo_pairs)} repositories with {max_workers} workers...")
    metrics_list = client.fetch_batch(repo_pairs, max_workers=max_workers)

    # ── Step 3: Score each repo ───────────────────────────────────────────────
    total = len(metrics_list)
    scored = []

    for i, metrics in enumerate(metrics_list):
        logger.info(f"Scoring [{i+1}/{total}]: {metrics.full_name}")
        result = analyze(metrics)
        scored.append(result)

        if progress_callback:
            progress_callback(i + 1, total, metrics.full_name)

    # ── Step 4: Merge parse errors back in order ──────────────────────────────
    # Build final list: scored repos + parse errors at the end
    final = scored + [r for _, r in parse_errors]

    return final
