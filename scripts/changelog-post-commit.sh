#!/usr/bin/env bash
set -euo pipefail

if ! command -v git-cliff >/dev/null 2>&1; then
  echo "post-commit: git-cliff not found, skipping changelog update" >&2
  exit 0
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

git-cliff --config cliff.toml --output "$tmp_file"

if diff -q "$tmp_file" CHANGELOG.md >/dev/null 2>&1; then
  exit 0
fi

cp "$tmp_file" CHANGELOG.md
git add CHANGELOG.md
git commit --amend --no-edit --no-verify
