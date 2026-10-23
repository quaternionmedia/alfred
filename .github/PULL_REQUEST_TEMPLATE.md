<!--
Delete any section that does not apply. An empty heading is worse than an
absent one -- it reads as an answer.
-->

## What this changes

<!-- What it does and why. If it fixes something, say what the symptom was:
     the next person searches for the symptom, not the fix. -->

## How it was verified

<!-- Commands run and what they reported, as output rather than assertion.
     "225 passed, 6 skipped, 19 xfailed" beats "tests pass". If something was
     not verified, say so here rather than leaving it to be assumed. -->

## Branch provenance

<!-- Paste the output of:
       python governance/qm/project-seed/ci/check_pr_base.py --base main --head <branch>

     It reports what this PR is based on, what it carries, who wrote each
     commit, which paths it touches, and whether any commit already belongs to
     another open PR. A branch cut from the wrong parent is internally
     consistent -- its tests pass and its lint is clean -- so nothing else
     catches it. -->

```
```

## Checklist

- [ ] Formatting and lint clean (`./al nox -s blacken`, `./al nox -s lint`)
- [ ] Backend suite run, with its numbers in the section above
- [ ] Browser suite run if the frontend changed (`./al test`, which builds its own stack)
- [ ] `docs/cookbook.md` regenerated if any e2e spec changed (`./al cookbook`)
- [ ] No co-author trailer naming an unmonitored address; tool involvement
      disclosed as a `Tools:` note instead
- [ ] Any submodule pointer bump points at a commit already merged and pushed
      on that submodule's remote

## Tools

<!-- Software substantially involved in producing this change, for provenance.
     Recorded, never credited: the human who ran it is the contributor. -->
