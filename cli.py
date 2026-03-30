#!/usr/bin/env python3
"""
cli.py — Command-line interface for the GitHub Repository Intelligence Analyzer.

Usage:
  python cli.py django/django pallets/flask
  python cli.py https://github.com/django/django --output report.json
  python cli.py --file repos.txt --output report.json
  python cli.py django/django --quiet
"""

import argparse
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

from analyzer.pipeline import run_analysis
from analyzer.reporter import to_json, to_markdown, print_rich_table, print_plain_table


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Repository Intelligence Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py django/django pallets/flask
  python cli.py https://github.com/torvalds/linux --output report.json
  python cli.py --file repos.txt
  python cli.py django/django --quiet --output report.json
        """
    )

    parser.add_argument(
        "repos", nargs="*",
        help="GitHub repo URLs or owner/repo shorthands"
    )
    parser.add_argument(
        "--file", "-f", metavar="FILE",
        help="Path to file with one repo URL per line"
    )
    parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="Write JSON report to this file (default: print to stdout)"
    )
    parser.add_argument(
        "--markdown", "-m", metavar="FILE",
        help="Write markdown summary to this file"
    )
    parser.add_argument(
        "--token", "-t", metavar="TOKEN",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=4,
        help="Concurrent fetch threads (default: 4)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress table output — only write files"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # ── Logging setup ─────────────────────────────────────────────────────────
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # ── Collect repo URLs ─────────────────────────────────────────────────────
    repo_urls = list(args.repos or [])

    if args.file:
        try:
            with open(args.file, "r") as f:
                file_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            repo_urls.extend(file_urls)
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)

    if not repo_urls:
        # Default demo repos if none provided
        repo_urls = [
            "c2siorg/Webiu",
            "pallets/flask",
            "django/django",
            "torvalds/linux",
            "sindresorhus/awesome",
        ]
        print("No repos specified. Running on 5 demo repos...\n")

    # ── Token ─────────────────────────────────────────────────────────────────
    token = args.token or os.getenv("GITHUB_TOKEN", "")
    if not token:
        print("⚠️  No GITHUB_TOKEN set. Rate limit: 60 req/hr (enough for ~3 repos).")
        print("   Set via: export GITHUB_TOKEN=your_token\n")

    # ── Run analysis ──────────────────────────────────────────────────────────
    print(f"Analyzing {len(repo_urls)} repositor{'y' if len(repo_urls)==1 else 'ies'}...\n")

    def progress(current, total, name):
        print(f"  [{current}/{total}] ✓ {name}")

    results = run_analysis(
        repo_urls,
        token=token,
        max_workers=args.workers,
        progress_callback=progress if not args.quiet else None,
    )

    print()

    # ── Output ────────────────────────────────────────────────────────────────
    if not args.quiet:
        print_rich_table(results)

    # JSON output
    json_str = to_json(results)
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"✅ JSON report written to: {args.output}")
    elif args.quiet:
        print(json_str)

    # Markdown output
    if args.markdown:
        md_str = to_markdown(results)
        with open(args.markdown, "w") as f:
            f.write(md_str)
        print(f"✅ Markdown report written to: {args.markdown}")

    # Exit code: 0 if all succeeded, 1 if any had errors
    has_errors = any(r.error for r in results)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
