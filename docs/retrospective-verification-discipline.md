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

The remedy is cheap and is not yet done: re-run both suites against a stack
brought up deliberately for the purpose, with its configuration asserted rather
than assumed, and report those numbers as the ones that count.

## For triage

1. The dev stack should not publish on default ports, or `./al dev` should
   refuse to start when something else already holds them and say what.
2. `ALFRED_DEV_SKIP_AUTH` should be impossible to leave set. Options: refuse to
   start if it has been on for more than one process lifetime, or drop it in
   favour of a disposable stack profile.
3. The suites should record what they ran against. A test run that cannot
   identify its subject is the failure mode this document exists about.
