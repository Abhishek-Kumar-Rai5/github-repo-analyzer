"""
reporter.py — Structured report generation.

Outputs:
  - JSON report (machine-readable, includes all sub-scores)
  - Terminal table (rich-formatted, human-readable)
  - Markdown summary (for README / committed sample outputs)
"""

import json
from datetime import datetime, timezone
from typing import Optional

from .models import AnalysisResult

# Try to import rich for pretty terminal output; fall back to plain text
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


DIFFICULTY_EMOJI = {
    "Beginner":     "🟢",
    "Intermediate": "🟡",
    "Advanced":     "🔴",
    "Too New":      "⚪",
    "Unknown":      "❓",
}

CONFIDENCE_COLOR = {
    "HIGH":   "green",
    "MEDIUM": "yellow",
    "LOW":    "red",
}


def to_dict(result: AnalysisResult) -> dict:
    """Convert one AnalysisResult to a JSON-serializable dict."""
    m = result.metrics
    return {
        "repository": {
            "full_name": m.full_name,
            "url": m.url,
            "description": m.description[:200] if m.description else "",
            "primary_language": m.primary_language,
            "languages": m.languages,
            "topics": m.topics,
            "license": m.license,
            "is_archived": m.is_archived,
            "is_fork": m.is_fork,
            "age_days": m.age_days,
            "days_since_last_push": m.days_since_push,
            "stars": m.stars,
            "forks": m.forks,
            "contributors_count": m.contributors_count,
            "commits_30d": m.commits_30d,
            "open_issues": m.open_issues,
            "closed_issues_30d": m.closed_issues_30d,
            "open_prs": m.open_prs,
            "merged_prs_30d": m.merged_prs_30d,
            "file_count": m.file_count,
            "repo_size_kb": m.repo_size_kb,
            "dependency_files": m.dependency_files,
            "tech_ecosystems": m.tech_ecosystems,
            "fetch_errors": m.fetch_errors,
        },
        "scores": {
            "activity_score": result.activity_score,
            "activity_breakdown": result.activity_breakdown.components if result.activity_breakdown else {},
            "complexity_score": result.complexity_score,
            "complexity_breakdown": result.complexity_breakdown.components if result.complexity_breakdown else {},
        },
        "classification": {
            "difficulty": result.difficulty,
            "confidence": result.confidence,
        },
        "observations": result.observations,
        "error": result.error,
    }


def to_json(results: list[AnalysisResult], indent: int = 2) -> str:
    """Serialize all results to a JSON string."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_repos": len(results),
        "summary": {
            "beginner": sum(1 for r in results if r.difficulty == "Beginner"),
            "intermediate": sum(1 for r in results if r.difficulty == "Intermediate"),
            "advanced": sum(1 for r in results if r.difficulty == "Advanced"),
            "errors": sum(1 for r in results if r.error),
        },
        "repositories": [to_dict(r) for r in results],
    }
    return json.dumps(report, indent=indent, default=str)


def to_markdown(results: list[AnalysisResult]) -> str:
    """Generate a markdown summary table for committed sample outputs."""
    lines = [
        "# GitHub Repository Intelligence Analyzer — Sample Report",
        f"\n_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n",
        "## Summary Table\n",
        "| Repository | Stars | Activity | Complexity | Difficulty | Confidence |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        m = r.metrics
        emoji = DIFFICULTY_EMOJI.get(r.difficulty, "❓")
        if r.error:
            lines.append(f"| {m.url} | — | — | — | ❌ Error | — |")
        else:
            lines.append(
                f"| [{m.full_name}]({m.url}) | ⭐ {m.stars:,} | "
                f"{r.activity_score:.1f} | {r.complexity_score:.1f} | "
                f"{emoji} {r.difficulty} | {r.confidence} |"
            )

    lines.append("\n## Detailed Reports\n")
    for r in results:
        if r.error:
            continue
        m = r.metrics
        emoji = DIFFICULTY_EMOJI.get(r.difficulty, "❓")
        lines.append(f"### {m.full_name}")
        lines.append(f"**URL:** {m.url}  ")
        lines.append(f"**Description:** {m.description or 'N/A'}  ")
        lines.append(f"**Primary Language:** {m.primary_language or 'N/A'}  ")
        lines.append(f"**Age:** {m.age_days} days | **Last Push:** {m.days_since_push} days ago  ")
        lines.append(f"**Stars:** {m.stars:,} | **Forks:** {m.forks:,} | **Contributors:** {m.contributors_count}  ")
        lines.append("")
        lines.append("#### Scores")
        lines.append(f"- **Activity Score:** {r.activity_score:.1f} / 100")
        if r.activity_breakdown:
            for k, v in r.activity_breakdown.components.items():
                lines.append(f"  - {k}: `{v}`")
        lines.append(f"- **Complexity Score:** {r.complexity_score:.1f} / 100")
        if r.complexity_breakdown:
            for k, v in r.complexity_breakdown.components.items():
                lines.append(f"  - {k}: `{v}`")
        lines.append("")
        lines.append(f"#### Classification: {emoji} {r.difficulty} (Confidence: {r.confidence})")
        lines.append("")
        lines.append("#### Observations")
        for obs in r.observations:
            lines.append(f"- {obs}")
        lines.append("")
        lines.append("---\n")

    return "\n".join(lines)


def print_rich_table(results: list[AnalysisResult]):
    """Print a beautiful rich-formatted summary table to terminal."""
    if not RICH_AVAILABLE:
        print_plain_table(results)
        return

    console = Console()
    table = Table(
        title="GitHub Repository Intelligence Report",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold white on dark_blue",
    )
    table.add_column("Repository", style="cyan bold", min_width=25)
    table.add_column("Stars", justify="right", style="yellow")
    table.add_column("Activity", justify="right")
    table.add_column("Complexity", justify="right")
    table.add_column("Difficulty", justify="center")
    table.add_column("Confidence", justify="center")
    table.add_column("Key Insight", min_width=35)

    for r in results:
        m = r.metrics
        if r.error:
            table.add_row(m.url, "—", "—", "—", "❌ Error", "—", r.error[:60])
            continue

        emoji = DIFFICULTY_EMOJI.get(r.difficulty, "❓")
        diff_color = {"Beginner": "green", "Intermediate": "yellow", "Advanced": "red"}.get(r.difficulty, "white")
        conf_color = CONFIDENCE_COLOR.get(r.confidence, "white")

        # Pick most interesting observation
        key_obs = r.observations[0] if r.observations else ""
        if len(key_obs) > 60:
            key_obs = key_obs[:57] + "..."

        table.add_row(
            m.full_name,
            f"{m.stars:,}",
            f"[{'green' if r.activity_score >= 60 else 'yellow' if r.activity_score >= 30 else 'red'}]{r.activity_score:.1f}[/]",
            f"[{'red' if r.complexity_score >= 65 else 'yellow' if r.complexity_score >= 30 else 'green'}]{r.complexity_score:.1f}[/]",
            f"[{diff_color}]{emoji} {r.difficulty}[/]",
            f"[{conf_color}]{r.confidence}[/]",
            key_obs,
        )

    console.print()
    console.print(table)
    console.print()

    # Print per-repo breakdowns
    for r in results:
        if r.error or not r.observations:
            continue
        m = r.metrics
        emoji = DIFFICULTY_EMOJI.get(r.difficulty, "❓")
        panel_text = Text()
        panel_text.append(f"Activity: {r.activity_score:.1f}  |  Complexity: {r.complexity_score:.1f}  |  {emoji} {r.difficulty} ({r.confidence} confidence)\n\n", style="bold")
        for obs in r.observations:
            panel_text.append(f"• {obs}\n", style="dim")
        console.print(Panel(panel_text, title=f"[bold cyan]{m.full_name}[/]", border_style="blue"))

    console.print()


def print_plain_table(results: list[AnalysisResult]):
    """Fallback plain-text table when rich is not available."""
    header = f"{'Repository':<35} {'Stars':>8} {'Activity':>10} {'Complexity':>12} {'Difficulty':<15} {'Confidence'}"
    print("\n" + "=" * len(header))
    print("GitHub Repository Intelligence Report")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for r in results:
        m = r.metrics
        if r.error:
            print(f"{m.url:<35} {'ERROR':>8} {'—':>10} {'—':>12} {'Unknown':<15} —")
        else:
            emoji = DIFFICULTY_EMOJI.get(r.difficulty, "?")
            print(
                f"{m.full_name:<35} {m.stars:>8,} "
                f"{r.activity_score:>10.1f} {r.complexity_score:>12.1f} "
                f"{emoji + ' ' + r.difficulty:<15} {r.confidence}"
            )
    print("=" * len(header) + "\n")
