# Questions a new developer asks

This page is for someone handed alfred's checkout who wants to change it. Each
question below is one a newcomer asks, with the command or the file that
settles it.

It is a map, not the rules. Where it sums up a rule it names the document that
owns it, and that document wins: `AGENTS.md` at the root of the repository,
and this project's records in `governance/qm/adr/`.

## Where the commands run

**Every `./al …` command runs at the root of alfred's checkout.** `./al` is a
`sh` script: on Linux, macOS, Git Bash and WSL it runs as it is, and in
PowerShell through the `al` function [Commands on each system](commands.md)
gives. `./al` with nothing after it lists every command.

## Getting going

**"I just cloned it. What do I run first?"**

`./al init`, then `ALFRED_DEV_SKIP_AUTH=1 ./al dev`, and browse to
<http://127.0.0.1:1732>. [Get started](start.md) walks it, and says what you
see when it worked.

**"Is that alfred answering, or something else on the port?"**

`curl 127.0.0.1:1732/openapi.json` names whatever answers: alfred says `Alfred
API`. A test result is only as good as your knowledge of what served it; the
[dev-server notes](dev-server.md) have the story behind that rule.

**"I edited `alfred/` and nothing changed."**

On Windows and macOS, `./al docker restart api`: uvicorn's reloader never
hears an edit through Docker's bind mount. If every request is then refused,
`./al docker logs api` names the syntax error.

**"Transcribe timeline says there is no audio engine."**

The dev stack alone has none. `./al family up` starts joe beside it and points
alfred at it ([The family dev loop](family.md)).

**"Which settings are there?"**

[Configuration](configuration.md), every one alfred reads, by what it is for.
A setting you add goes on that page and in the stacks' lists, or
`tests/unit/test_docs_accounted.py` and `tests/unit/test_stack_settings.py`
fail.

## Testing a change

**"How do I run the tests?"**

`./al loop`: the host's quick tests, the API suite, the browser suite and the
docs build, side by side, one line each as they finish ([The test
loop](loop.md)). `./al loop --stack --keep` then leaves the app up with joe, to
try by hand.

**"Just one browser test?"**

`./al loop one --only e2e --grep the.words.of.its.title`: dots stand for the
spaces, which the loop's `--grep` does not take.

**"What does the browser suite check?"**

[The browser suite](cookbook.md): one line per spec. The user journeys each
name the specs that walk them.

**"Did my change break otto, vox, joe or qmcp?"**

`./al family loop`: each one's quick suite, then joe and the dev stack
together, a live check, and down. `./al family` first, to see which checkout
of each it will use.

**"The screenshots in the docs show the old screen."**

`./al recipes`, against a dev stack, retakes them and records the
walkthroughs; the guide's own pictures come from `./al loop shots --only e2e
--projects docs --grep making.a.video`. [Editing tools](tools.md#the-pictures)
says which spec takes which.

## Before you push

**"Will CI reject anything?"**

The pull-request checklist (`.github/PULL_REQUEST_TEMPLATE.md`) is the list:

- Black with `-S`, and ruff: `./al nox -s blacken`, then `./al nox -s lint`;
- the cookbook regenerated when a spec changed: `./al cookbook`;
- no co-author trailer naming an unmonitored address, and tool involvement as
  a `Tools:` note (`AGENTS.md`, item 4);
- a submodule pin only on a commit already pushed to that engine.

**"Who merges it?"**

Not you. Everything arrives as a pull request on a branch of its own, and the
codeowners merge (`AGENTS.md`, item 3).

**"I am adding a dependency."**

Read the adoption-scope record in `governance/qm/adr/` first, then
[Dependencies](dependencies.md): pdm, not pip, and the exported lockfiles the
image installs with `--no-deps`. No frontend asset from a CDN.

**"Can I print that token while debugging?"**

No secret goes into a terminal, a log, a commit, a pull request or a report
(`AGENTS.md`, item 8). List variables by name, write `sig=…` for a signed URL,
and use `docker compose config --no-interpolate`. `./al family` and
`./al loop` redact what they print.

## Where things live

**"Where does the video work happen?"**

In otto, through its public API: renders, preview frames, a timeline's sound,
probing a file, the demo clips. alfred imports no media library and runs no
ffmpeg; what alfred needs that otto lacks is a change to otto, pinned here.
Each of those calls blocks, and `tests/unit/test_blocking_calls.py` keeps
them off the event loop.

**"Where does the audio engine get called?"**

Only in `alfred/core/utils/audio_engine.py`, through vox
([Captions](captions.md#the-audio-engine)).

**"How are the images and stacks put together?"**

[Images and stacks](build.md): the image, each compose file, the suites'
stacks, and CI.

**"Who can see a project?"**

The account that made it, and superusers ([Ownership](ownership.md)).

*What this page cannot do:* stand in for `AGENTS.md`, which an agent reads
before its first edit, or for the records, which decide what is allowed.
