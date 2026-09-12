#!/usr/bin/sh
# Install the repo's tracked git hooks into the local git dir (Q3-B / B4).
# Re-run after cloning. `git rev-parse --git-path` resolves worktrees/submodules.
set -eu
_repo_root=$(git rev-parse --show-toplevel)
_hook_path=$(git rev-parse --git-path hooks/pre-commit)
_src="$_repo_root/scripts/git-hooks/pre-commit"
mkdir -p "$(dirname "$_hook_path")"
cp "$_src" "$_hook_path"
chmod +x "$_hook_path"
printf 'installed: %s -> %s\n' "$_src" "$_hook_path"
