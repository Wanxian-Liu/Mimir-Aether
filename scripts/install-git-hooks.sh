#!/usr/bin/sh
# Install the repo's tracked git hooks (Q3-B / B4; chain-safe since X3-b, 2026-09-12).
#
# Why a chain instead of a plain copy: this repo's hook is not the only hook a
# repository may have. `~/wiki` carries its own `.contracts/` enforcement hook,
# and the old version of this script did `cp` with no detection -- installing
# into such a repo silently destroyed the existing hook (found in the X3 audit:
# "install script has no backup logic"). So now: detect -> backup -> chain.
#
# Behaviour
#   1. always (re)install the Mimir audit hook as  <hooks>/pre-commit-mimir-audit
#   2. if <hooks>/pre-commit exists and is NOT ours:
#        - copy it to <hooks>/pre-commit.bak-<UTC stamp>   (record)
#        - preserve it as <hooks>/pre-commit-local         (executed by the chain)
#   3. write <hooks>/pre-commit as a chain that runs pre-commit-local first and
#      then the audit hook, propagating the first non-zero status
#   4. idempotent: re-running refreshes pre-commit-mimir-audit and never touches
#      an already-preserved pre-commit-local
#
# Usage
#   sh scripts/install-git-hooks.sh                 # install into this repo
#   sh scripts/install-git-hooks.sh --repo ~/wiki   # install into another repo
#   MIMIR_HOOKS_NO_BACKUP=1 sh scripts/install-git-hooks.sh   # skip the .bak copy
#
# Re-run after cloning. The hook SOURCE is always this script's own repository
# (the target repo may have no scripts/git-hooks of its own).
set -eu

MIMIR_HOOK_MARKER="# MimirAether hook chain (install-git-hooks.sh)"
AUDIT_HOOK_NAME="pre-commit-mimir-audit"
LOCAL_HOOK_NAME="pre-commit-local"

_target_arg=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      [ $# -ge 2 ] || { printf 'usage: install-git-hooks.sh [--repo <path>]\n' >&2; exit 2; }
      _target_arg="$2"; shift 2 ;;
    -h|--help)
      printf 'usage: install-git-hooks.sh [--repo <path>]\n'; exit 0 ;;
    *)
      printf 'install-git-hooks.sh: unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

_script_repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
_src="$_script_repo/scripts/git-hooks/pre-commit"
[ -f "$_src" ] || { printf 'install-git-hooks.sh: missing hook source %s\n' "$_src" >&2; exit 1; }

_target_repo="${_target_arg:-$_script_repo}"
_repo_root=$(git -C "$_target_repo" rev-parse --show-toplevel)
_hook_rel=$(git -C "$_target_repo" rev-parse --git-path hooks)
case "$_hook_rel" in
  /*) _hooks_dir="$_hook_rel" ;;
  *)  _hooks_dir="$_repo_root/$_hook_rel" ;;
esac
_hook_path="$_hooks_dir/pre-commit"
mkdir -p "$_hooks_dir"

_stamp=$(date -u +%Y%m%d-%H%M%S)

# 1. the audit hook itself (refreshed every run)
cp "$_src" "$_hooks_dir/$AUDIT_HOOK_NAME"
chmod +x "$_hooks_dir/$AUDIT_HOOK_NAME"
printf 'installed: %s -> %s\n' "$_src" "$_hooks_dir/$AUDIT_HOOK_NAME"

# 2. detect an existing pre-commit and preserve it instead of overwriting
_preserved=0
if [ -f "$_hook_path" ]; then
  if grep -qF "$MIMIR_HOOK_MARKER" "$_hook_path" 2>/dev/null; then
    printf 'detected : %s is already a Mimir chain (refresh only)\n' "$_hook_path"
  elif grep -qF 'MimirAether pre-commit hook' "$_hook_path" 2>/dev/null; then
    printf 'detected : %s is a plain Mimir audit install -> converting to chain\n' "$_hook_path"
  else
    if [ "${MIMIR_HOOKS_NO_BACKUP:-0}" != "1" ]; then
      cp "$_hook_path" "$_hook_path.bak-$_stamp"
      printf 'backup   : %s.bak-%s\n' "$_hook_path" "$_stamp"
    fi
    if [ -f "$_hooks_dir/$LOCAL_HOOK_NAME" ]; then
      printf 'preserve : %s already exists (left untouched)\n' "$_hooks_dir/$LOCAL_HOOK_NAME"
    else
      cp "$_hook_path" "$_hooks_dir/$LOCAL_HOOK_NAME"
      chmod +x "$_hooks_dir/$LOCAL_HOOK_NAME"
      printf 'preserve : %s -> %s\n' "$_hook_path" "$_hooks_dir/$LOCAL_HOOK_NAME"
    fi
    _preserved=1
  fi
fi

# 3. the chain (generated file -- edit the tracked hook and re-run instead)
cat > "$_hook_path" <<'MIMIR_CHAIN_EOF'
#!/usr/bin/sh
# MimirAether hook chain (install-git-hooks.sh)
# Generated file. Runs the repository's own hook (preserved as pre-commit-local)
# first, then the Mimir audit/attribution hook, and propagates the first
# non-zero status. Do not edit: edit the tracked hook in the MimirAether repo
# (scripts/git-hooks/pre-commit) and re-run scripts/install-git-hooks.sh.
_hook_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
_rc=0
if [ -x "$_hook_dir/pre-commit-local" ]; then
  "$_hook_dir/pre-commit-local" "$@"
  _r=$?
  if [ "$_r" -ne 0 ] && [ "$_rc" -eq 0 ]; then _rc=$_r; fi
fi
if [ -x "$_hook_dir/pre-commit-mimir-audit" ]; then
  "$_hook_dir/pre-commit-mimir-audit" "$@"
  _r=$?
  if [ "$_r" -ne 0 ] && [ "$_rc" -eq 0 ]; then _rc=$_r; fi
fi
exit "$_rc"
MIMIR_CHAIN_EOF
chmod +x "$_hook_path"

if [ "$_preserved" = "1" ]; then
  printf 'installed: chain -> %s (existing hook preserved as %s)\n' \
    "$_hook_path" "$LOCAL_HOOK_NAME"
else
  printf 'installed: chain -> %s\n' "$_hook_path"
fi
