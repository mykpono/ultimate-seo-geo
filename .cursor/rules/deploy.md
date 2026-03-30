---
description: When the user says "deploy", "ship", "push", or "release"
globs:
alwaysApply: false
---

# Deploy

Read and follow `RELEASE.md` at the repo root. It is the single source of truth for all deployment steps.

At minimum, never skip these steps:
1. Sync plugin bundle (step 2 in RELEASE.md)
2. Validate with `python3 scripts/check-plugin-sync.py` (step 3)
3. Commit and push (step 6)
4. **Create GitHub Release** (step 6a — required, never skip)
5. Verify with `python3 scripts/check_github_release.py` (step 6c)
