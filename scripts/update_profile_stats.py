#!/usr/bin/env python3
"""Refresh the profile README from GitHub's official contribution data."""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_URL = "https://api.github.com/graphql"
README_PATH = Path("README.md")
START_MARKER = "<!-- GITHUB_ACTIVITY:START -->"
END_MARKER = "<!-- GITHUB_ACTIVITY:END -->"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      commitContributionsByRepository { contributions { totalCount } }
      issueContributions { totalCount }
      pullRequestContributions { totalCount }
      pullRequestReviewContributions { totalCount }
    }
  }
}
"""


def fetch_stats(login: str, token: str) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    variables = {
        "login": login,
        "from": (now - timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    }
    body = json.dumps({"query": QUERY, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Bilal-Lodhi-profile-stats",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {login}")

    collection = user["contributionsCollection"]
    commits = sum(
        repository["contributions"]["totalCount"]
        for repository in collection["commitContributionsByRepository"]
    )
    return {
        "contributions": collection["contributionCalendar"]["totalContributions"],
        "commits": commits,
        "pull_requests": collection["pullRequestContributions"]["totalCount"],
        "issues": collection["issueContributions"]["totalCount"],
        "reviews": collection["pullRequestReviewContributions"]["totalCount"],
    }


def render_block(stats: dict[str, int]) -> str:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "\n".join(
        [
            START_MARKER,
            f"- **Contributions in the last 365 days:** `{stats['contributions']:,}`",
            f"- **Commits in the last 365 days:** `{stats['commits']:,}`",
            f"- **Pull requests opened:** `{stats['pull_requests']:,}`",
            f"- **Issues opened:** `{stats['issues']:,}`",
            f"- **Pull request reviews:** `{stats['reviews']:,}`",
            f"- _Fetched from GitHub's official contribution data on `{fetched_at}`._",
            END_MARKER,
        ]
    )


def update_readme(stats: dict[str, int]) -> None:
    with README_PATH.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("README activity markers are missing or out of order")
    end += len(END_MARKER)
    replacement = (render_block(stats) + "\n").replace("\n", newline)
    updated = text[:start] + replacement + text[end:]
    with README_PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)


def main() -> None:
    token = os.environ.get("GH_TOKEN")
    login = os.environ.get("PROFILE_LOGIN", "Bilal-Lodhi")
    if not token:
        raise RuntimeError("GH_TOKEN is required")
    update_readme(fetch_stats(login, token))


if __name__ == "__main__":
    main()