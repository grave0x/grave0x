#!/usr/bin/env python3
"""Regenerate the 'Recent activity' changelog section of the profile README.

Fetches the user's most recently pushed public repos (plus latest release tags)
from the GitHub API and rewrites the block between the CHANGELOG markers.
Uses only the stdlib. Requires a token (GITHUB_TOKEN) for reliable rate limits;
without one it falls back to the public API limit (60 req/hr, fine locally).
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date

USER = "grave0x"
README = "README.md"
MAX_REPOS = 8

START = "<!-- CHANGELOG:START -->"
END = "<!-- CHANGELOG:END -->"


def api(path: str):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def esc(s: str) -> str:
    return s.replace("|", "\\|")


def main() -> int:
    try:
        repos = api(f"/users/{USER}/repos?sort=pushed&per_page={MAX_REPOS}&type=owner")
    except Exception as exc:
        print(f"failed to fetch repos: {exc}", file=sys.stderr)
        return 1  # leave the README untouched on failure

    repos = [r for r in repos if not r.get("fork") and r["full_name"] != f"{USER}/grave0x"]
    if not repos:
        print("no public repos returned", file=sys.stderr)
        return 1

    rows = []
    for r in repos:
        tag = ""
        try:
            rel = api(f"/repos/{r['full_name']}/releases/latest")
            tag = rel.get("tag_name", "") or ""
        except Exception:
            tag = ""
        pushed = (r.get("pushed_at") or "")[:10]
        lang = r.get("language") or "—"
        stars = r.get("stargazers_count", 0)
        link = f"[{esc(r['name'])}]({r['html_url']})"
        rows.append(
            f"| {link} | `{esc(tag) if tag else '—'}` | {pushed} | {lang} | ★ {stars} |"
        )

    table = "\n".join(
        [
            "| repo | latest release | pushed | language | stars |",
            "|---|---|---|---|---|",
            *rows,
            "",
            f"*last updated {date.today().isoformat()} by [github-actions](https://github.com/features/actions)*",
        ]
    )

    with open(README, encoding="utf-8") as f:
        content = f.read()

    new_section = f"## Recent activity\n\n{START}\n{table}\n{END}\n"
    if START in content and END in content:
        content = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            START + "\n" + table + "\n" + END,
            content,
            flags=re.S,
        )
    else:
        anchor = "## Stats"
        if anchor in content:
            content = content.replace(anchor, new_section + "\n" + anchor, 1)
        else:
            content = content.rstrip() + "\n\n" + new_section

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"changelog updated: {len(rows)} repos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
