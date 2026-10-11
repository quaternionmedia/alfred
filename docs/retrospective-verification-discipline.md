# Retrospective: I verified against a server I never identified

**Status:** input for governance triage. Not a decision record.
**Scope:** the verification method used across the `release/0.3.0` work
**Tools:** written by the AI coding agent that made the mistake

---

## What I said

> **Two problems, and one is serious. `ALFRED_DEV_SKIP_AUTH=1` is set again.**

In bold. "Again", as though the environment variable had come back on its own.

## What was actually true

I set it. Earlier in the same session I ran:

```sh
ALFRED_DEV_SKIP_AUTH=1 docker compose -f docker-compose.yml -f dev.yml up -d
```

to check that the auth bypass worked. Every later `docker compose up -d` reused
that container rather than recreating it, so the variable stayed in its
environment. The state I reported as a mystery was residue I left.

There was no second stack in the end — one compose project, one API container.
But I did not know that when I wrote the sentence, and nothing I had done would
have told me. I inspected a container with `docker compose exec` and I fetched
`http://localhost:8000` with curl, and I never once established that those two
things were the same process.

## Why that is the serious part

Port 8000 is a default. Anything can hold it: another checkout of this
repository, a stray container from a previous `up`, a `uvicorn` somebody
started by hand. `curl localhost:8000` answers whatever is bound, and
`docker compose exec` talks to whatever compose thinks is current. Those can
disagree, and nothing in either command tells you they have.

So the failure is not that a flag was set. It is that **every number I reported
in this branch came from a server I had not identified.** "225 passed", "134
e2e", "anonymous callers are refused" — each of those was measured against
whatever was answering that port at that moment. Most of the time that was the
right thing. I cannot demonstrate it was every time, and the one occasion I
caught it, a full suite run had already happened with authentication disabled.
I found that by accident, because an unrelated test failed.

A test suite that cannot name the thing it tested is not evidence. It is a
number with a story attached.

## The part that should have been impossible to miss

Early in this same branch I found the identical class of bug and wrote it into
`AGENTS.md` myself:

> **Port 27017.** `dev.yml` publishes MongoDB on the host. If anything else is
> already bound there [...] the stack fails with `Bind for 0.0.0.0:27017
> failed: port is already allocated`, and the message names the port but not
> the culprit.

I documented that a default port is a shared resource whose occupant you have
to check, filed it as a first-run trap, and then spent the rest of the session
treating `localhost:8000` as though it were unambiguously mine. Writing a
lesson down is not the same as holding it.

I also had a second warning and dismissed it. Earlier the same day I found the
bypass on, restarted, re-ran, and reported that the suite went from 100 passing
to 99 with authentication enabled. That is a direct measurement that my
environment had been lying to me, and I treated it as a one-off to be corrected
rather than as evidence that my method had no way of catching it.

## What I should have done

- **Bound the dev stack to a port nobody else would take**, or checked what
  held 8000 before assuming it was mine.
- **Never set a security-relevant flag on a long-lived container.** A bypass
  worth testing is worth testing in a disposable stack that cannot outlive the
  check.
- **Recorded the identity of the server with each result** — a startup
  fingerprint or a `/health` response echoing the configuration — so a claim
  like "anonymous callers are refused" carries the thing it was measured
  against.
- **Asked what changed rather than reporting that something had changed.** The
  bold sentence was a conclusion. Two commands would have turned it into a
  cause, and one of them would have named me.

## What this costs the branch

The functional findings stand: the fixes are real, the defects were real, and
the code is what it is. What is weakened is the evidence, in a specific and
limited way — every test result in this branch should be read as "passed
against the stack that was answering :8000", not "passed against a known
configuration".

The remedy is cheap: re-run both suites against a stack brought up
deliberately for the purpose, with its configuration asserted rather than
assumed, and report those numbers as the ones that count.

## The remedy, carried out

It was worth doing, because the collision was real and still live.

`localhost:8000` was being served by **Apothecary API** — another QM project,
identified by fetching `/openapi.json` and reading the title, which is the
check this document says should have happened at the start. Alfred's own
container was healthy the whole time and answering on its own network. So the
suspicion above was not paranoia about a hypothetical; the port had an
occupant, and I had been measuring against it.

The stack was moved to a port chosen for the purpose, its identity asserted
(`Alfred API`, version 0.3.0), the auth bypass confirmed unset, and both
suites re-run:

| | Before | After |
|---|---|---|
| Backend (`./al pytest`) | 104 passed, 4 failed, 10 errors | **229 passed**, 2 skipped, 19 xfailed |
| Browser (Playwright) | 134 passed | **140 passed** |
| Ruff | failed on a usage error | clean |
| Black | 18 files, tests only | 45 files, application included |

The backend numbers moved that far because verifying properly surfaced four
defects that had nothing to do with ports, and would have shipped:

- `passlib` imports `pkg_resources`, which setuptools removed in v81, so every
  module touching authentication failed to import — reported as ten unrelated
  broken test modules.
- The suite imported `otto` from site-packages rather than the vendored
  submodule, testing a different copy of the engine than the image runs.
- The vendored engine was installed without its `[render]` extra, so `gizeh`
  was missing and every text template silently rendered to `None`.
- The lint session ran `ruff <path>`, removed in ruff 0.5, and had been
  failing with a usage message rather than linting. Both it and Black also ran
  from `tests/`, so neither had ever examined `alfred/`.

That is the argument for the discipline, made better than the argument I made
for it above: I framed unverified measurement as a threat to *credibility*.
The larger cost is that it hides defects. Four gates were broken, and a green
number kept anyone from looking.

## For triage

1. ~~The dev stack should not publish on default ports, or `./al dev` should
   refuse to start when something else already holds them and say what.~~
   **Done.** Every published port is overridable (`ALFRED_PORT`,
   `ALFRED_DB_PORT`, `ALFRED_HMR_PORT`) and `./al dev` refuses to start on an
   occupied port, naming the occupant from its OpenAPI title.
2. `ALFRED_DEV_SKIP_AUTH` should be impossible to leave set. Options: refuse to
   start if it has been on for more than one process lifetime, or drop it in
   favour of a disposable stack profile. **Still open.**
3. The suites should record what they ran against. A test run that cannot
   identify its subject is the failure mode this document exists about.
   **Still open** — done by hand here, not yet automatic. The cheap version is
   a fixture that fetches `/openapi.json` once and fails the run if the title
   is not Alfred's.
4. New, and the one I would raise first: **the tool versions in
   `tests/noxfile.py` were unpinned**, so two of these four defects were
   upstream releases arriving on a morning nobody chose. They are pinned now,
   but the same pattern should be looked for elsewhere.
