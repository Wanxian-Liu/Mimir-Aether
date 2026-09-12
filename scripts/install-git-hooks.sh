#!/usr/bin/sh
# Install the repo's tracked git hooks (Q3-B / B4; chain-safe since X3-b, 2026-09-12;
# A2 commit-msg added 2026-09-13).
#
# Why a chain instead of a plain copy: this repo's hook is not the only hook a
# repository may have. `~/wiki` carries its own `.contracts/` enforcement hook,
# and the old version of this script did `cp` with no detection -- installing
# into such a repo silently destroyed the existing hook (found in the X3 audit:
# "install script has no backup logic"). So now: detect -> backup -> chain.
#
# Hooks installed (both chained, both non-blocking unless the hook itself says so)
#   pre-commit  -> pre-commit-mimir-audit  (attribution guard: foreign-amend block)
#   commit-msg  -> commit-msg-mimir-sign   (attribution trailer: Agent: <id>)
#
# Behaviour (per hook kind)
#   1. always (re)install the Mimir hook as  <hooks>/<kind>-mimir-<audit|sign>
#   2. if <hooks>/<kind> exists and is NOT ours:
#        - copy it to <hooks>/<kind>.bak-<UTC stamp>   (record)
#        - preserve it as <hooks>/<kind>-local         (executed by the chain)
#   3. write <hooks>/<kind> as a chain that runs <kind>-local first and then the
#      Mimir hook, propagating the first non-zero status
#   4. idempotent: re-running refreshes the Mimir hooks and never touches an
#      already-preserved <kind>-local
#
# Usage
#   sh scripts/install-git-hooks.sh                     # install into this repo
#   sh scripts/install-git-hooks.sh --repo ~/wiki       # install into another repo
#   sh scripts/install-git-hooks.sh --only commit-msg   # one hook kind only
#   MIMIR_HOOKS_NO_BACKUP=1 sh scripts/install-git-hooks.sh   # skip the .bak copy
#
# Re-run after cloning. The hook SOURCE is always this script's own repository
# (the target repo may have no scripts/git-hooks of its own).
set -eu

MIMIR_HOOK_MARKER="# MimirAether hook chain (install-git-hooks.sh)"

_target_arg=""
_only=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      [ $# -ge 2 ] || { printf 'usage: install-git-hooks.sh [--repo <path>] [--only pre-commit|commit-msg]\n' >&2; exit 2; }
      _target_arg="$2"; shift 2 ;;
    --only)
      [ $# -ge 2 ] || { printf 'usage: install-git-hooks.sh [--repo <path>] [--only pre-commit|commit-msg]\n' >&2; exit 2; }
      _only="$2"; shift 2 ;;
    -h|--help)
      printf 'usage: install-git-hooks.sh [--repo <path>] [--only pre-commit|commit-msg]\n'; exit 0 ;;
    *)
      printf 'install-git-hooks.sh: unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

case "$_only" in
  ""|pre-commit|commit-msg) ;;
  *) printf 'install-git-hooks.sh: --only must be pre-commit or commit-msg\n' >&2; exit 2 ;;
esac

_script_repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

_target_repo="${_target_arg:-$_script_repo}"
_repo_root=$(git -C "$_target_repo" rev-parse --show-toplevel)
_hook_rel=$(git -C "$_target_repo" rev-parse --git-path hooks)
case "$_hook_rel" in
  /*) _hooks_dir="$_hook_rel" ;;
  *)  _hooks_dir="$_repo_root/$_hook_rel" ;;
esac
mkdir -p "$_hooks_dir"

_stamp=$(date -u +%Y%m%d-%H%M%S)

# install_one <kind> <src-file> <installed-name> <legacy-marker>
install_one() {
  _kind="$1"; _src="$2"; _installed="$3"; _legacy_marker="$4"
  [ -f "$_src" ] || { printf 'install-git-hooks.sh: missing hook source %s\n' "$_src" >&2; exit 1; }
  _hook_path="$_hooks_dir/$_kind"
  _local_name="$_kind-local"

  # 1. the Mimir hook itself (refreshed every run)
  cp "$_src" "$_hooks_dir/$_installed"
  chmod +x "$_hooks_dir/$_installed"
  printf 'installed: %s -> %s\n' "$_src" "$_hooks_dir/$_installed"

  # 2. detect an existing hook and preserve it instead of overwriting
  _preserved=0
  if [ -f "$_hook_path" ]; then
    if grep -qF "$MIMIR_HOOK_MARKER" "$_hook_path" 2>/dev/null; then
      printf 'detected : %s is already a Mimir chain (refresh only)\n' "$_hook_path"
    elif grep -qF "$_legacy_marker" "$_hook_path" 2>/dev/null; then
      printf 'detected : %s is a plain Mimir install -> converting to chain\n' "$_hook_path"
    else
      if [ "${MIMIR_HOOKS_NO_BACKUP:-0}" != "1" ]; then
        cp "$_hook_path" "$_hook_path.bak-$_stamp"
        printf 'backup   : %s.bak-%s\n' "$_hook_path" "$_stamp"
      fi
      if [ -f "$_hooks_dir/$_local_name" ]; then
        printf 'preserve : %s already exists (left untouched)\n' "$_hooks_dir/$_local_name"
      else
        cp "$_hook_path" "$_hooks_dir/$_local_name"
        chmod +x "$_hooks_dir/$_local_name"
        printf 'preserve : %s -> %s\n' "$_hook_path" "$_hooks_dir/$_local_name"
      fi
      _preserved=1
    fi
  fi

  # 3. the chain (generated file -- edit the tracked hook and re-run instead)
  _chain_local="$_local_name"
  _chain_mimir="$_installed"
  {
    printf '#!/bin/sh\n'
    printf '%s\n' "$MIMIR_HOOK_MARKER"
    printf '# Generated file. Runs the repository'"'"'s own hook (preserved as %s)\n' "$_chain_local"
    printf '# first, then the Mimir %s hook, and propagates the first\n' "$_kind"
    printf '# non-zero status. Do not edit: edit the tracked hook in the MimirAether repo\n'
    printf '# (scripts/git-hooks/%s) and re-run scripts/install-git-hooks.sh.\n' "$_kind"
    printf '_hook_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
    printf '_rc=0\n'
    printf 'if [ -x "$_hook_dir/%s" ]; then\n' "$_chain_local"
    printf '  "$_hook_dir/%s" "$@"\n' "$_chain_local"
    printf '  _r=$?\n'
    printf '  if [ "$_r" -ne 0 ] && [ "$_rc" -eq 0 ]; then _rc=$_r; fi\n'
    printf 'fi\n'
    printf 'if [ -x "$_hook_dir/%s" ]; then\n' "$_chain_mimir"
    printf '  "$_hook_dir/%s" "$@"\n' "$_chain_mimir"
    printf '  _r=$?\n'
    printf '  if [ "$_r" -ne 0 ] && [ "$_rc" -eq 0 ]; then _rc=$_r; fi\n'
    printf 'fi\n'
    printf 'exit "$_rc"\n'
  } > "$_hook_path"
  chmod +x "$_hook_path"

  if [ "$_preserved" = "1" ]; then
    printf 'installed: chain -> %s (existing hook preserved as %s)\n' "$_hook_path" "$_local_name"
  else
    printf 'installed: chain -> %s\n' "$_hook_path"
  fi
}

if [ "$_only" != "commit-msg" ]; then
  install_one "pre-commit" \
    "$_script_repo/scripts/git-hooks/pre-commit" \
    "pre-commit-mimir-audit" \
    "MimirAether pre-commit hook"
fi

if [ "$_only" != "pre-commit" ]; then
  install_one "commit-msg" \
    "$_script_repo/scripts/git-hooks/commit-msg" \
    "commit-msg-mimir-sign" \
    "MimirAether commit-msg hook"
fi
