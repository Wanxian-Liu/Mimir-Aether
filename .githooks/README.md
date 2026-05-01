# Git hooks (optional, free)

**pre-push** runs `./run_ralph_tier0.sh` so you do not push broken agent code by accident (same checks as CI).

Enable in this clone:

```bash
git config core.hooksPath .githooks
```

Skip once if needed:

```bash
SKIP_RALPH_PRE_PUSH=1 git push
```
