#!/usr/bin/env bash
# scripts/release.sh — bump version, tag, push. The release workflow handles the rest.
#
# Usage: scripts/release.sh 0.3.0
#
# What this does:
#   1. Verifies the working tree is clean and on main.
#   2. Updates `version` in pyproject.toml + server.json.
#   3. Commits the bump and creates an annotated tag vX.Y.Z.
#   4. Pushes main and the tag.
#
# Then GitHub Actions (`.github/workflows/release.yml`) takes over:
#   tests → build → publish to PyPI → publish to MCP Registry → create Release.

set -euo pipefail

NEW="${1:-}"
if [[ -z "$NEW" ]]; then
    echo "usage: $0 <new-version>   (e.g. 0.3.0)" >&2
    exit 1
fi

if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
    echo "error: '$NEW' is not a valid semver" >&2
    exit 1
fi

cd "$(git rev-parse --show-toplevel)"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "error: working tree is dirty" >&2
    git status --short >&2
    exit 1
fi

if [[ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]]; then
    echo "error: not on main" >&2
    exit 1
fi

git pull --ff-only origin main

CURRENT=$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)
if [[ "$CURRENT" == "$NEW" ]]; then
    echo "error: pyproject.toml is already at $NEW" >&2
    exit 1
fi

echo "Bumping $CURRENT → $NEW"

# pyproject.toml
sed -i.bak "s/^version = \".*\"$/version = \"$NEW\"/" pyproject.toml
rm pyproject.toml.bak

# server.json (top-level + every package version)
jq --arg v "$NEW" '.version = $v | (.packages[].version) = $v' server.json > server.json.tmp
mv server.json.tmp server.json

git add pyproject.toml server.json
git commit -m "chore: release v$NEW"
git tag -a "v$NEW" -m "v$NEW"
git push origin main
git push origin "v$NEW"

echo
echo "✓ Pushed v$NEW. Watch the release workflow:"
echo "  https://github.com/dioptx/web3-docs/actions/workflows/release.yml"
