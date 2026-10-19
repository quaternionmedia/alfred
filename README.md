# alfred

> *"Drama is life with all the dull bits cut out."*
>
> ~ Alfred Hitchcock

Alfred is a browser video editor for quick editing from anywhere, mobile
devices included. The browser edits the timeline; every preview and render is
made by an Alfred server you run yourself, with cloud storage optional.

Demo at [alfred.quaternion.media](https://alfred.quaternion.media)

## Shape

A small **control plane** (`alfred/`) orchestrates two engines side by side.
**otto** draws the picture: the render engine, published as `al-otto` and
vendored at `alfred/otto`. **vox** carries the sound: QM's audio-engine seam,
vendored at `alfred/vox`, driving an engine such as joe over HTTP. The control
plane owns auth, project, render and caption lifecycle, and orchestration.
Every frame, render and timeline sound is otto's, and so are what a library
file holds, the demo clips and what a render's quality means to the encoder;
alfred imports no media library and runs no ffmpeg. `website/` is a mithril
SPA built with parcel.

Captions are typed, imported from SubRip, WebVTT or JSON, or transcribed from
the timeline's sound by the audio engine; otto draws them into renders.
[docs/captions.md](docs/captions.md) covers them and how to point alfred at joe.

The project is governed by the [Quaternion Media
constitution](https://github.com/quaternionmedia/qm), vendored at
`governance/qm`. Start at [AGENTS.md](AGENTS.md): it is the entry point for
contributors and coding agents alike, and names the known governance gaps.

## Clone

```sh
git clone --recurse-submodules https://github.com/quaternionmedia/alfred.git
cd alfred
git submodule update --init --recursive   # only if cloned without submodules
./al init                                 # install website dependencies
```

On Windows, `CLAUDE.md` and `.github/copilot-instructions.md` are symlinks;
see [AGENTS.md](AGENTS.md) for the one-time `core.symlinks` step.

## Common commands

Everything routes through `./al`. Run it with no arguments for the full list.

| Command | What it does |
|---|---|
| `./al init` | Install website dependencies |
| `./al dev` | Run the dev stack; app on http://localhost:8000 (`ALFRED_PORT` to move it) |
| `./al dev --build` | Rebuild images first |
| `./al stop` | Stop the dev stack |
| `./al demo` | Download demo media into `videos/` (needs network; the app can generate its own) |
| `./al pytest` | API test suite, in Docker |
| `./al test` | End-to-end suite (Playwright), in Docker |
| `./al nox -s lint` | Ruff |
| `./al nox -s blacken` | Black (`-S`) |
| `./al docs` | Serve the docs locally on :4000 |
| `./al prod` | Production stack; expects a running traefik and the production `ALFRED_SECRET_KEY` exported |
| `./al flower` | Celery monitoring on :5555; needs the dev stack for its broker |
| `./al cookbook` | Regenerate `docs/cookbook.md` from the e2e specs |
| `./al recipes` | Against a running stack: record the recipes as GIFs into `docs/recipes/`, take the screenshots into `docs/assets/screens/`, and regenerate the cookbook |
| `./al install <pkg>` | Add a website dependency |
| `./al family` | alfred with otto, vox, joe, qmcp and the rest: status, quick suites, the stack wired to joe, a live check ([docs/family.md](docs/family.md)) |

`./al dev` publishes on 8000, 8001 and 27017, on `127.0.0.1` only. It refuses
to start on an occupied port and names what holds it; move the port rather
than fight for it (`ALFRED_PORT=8100 ./al dev`, and `ALFRED_DB_PORT` /
`ALFRED_HMR_PORT` for the others). `ALFRED_BIND=0.0.0.0 ./al dev` publishes on
every interface for that run, to try the app from a phone; with
`ALFRED_DEV_SKIP_AUTH=1`, that makes anyone who can reach it a superuser. The
database stays on loopback either way. The dev-server notes in
[AGENTS.md](AGENTS.md) say why each of these matters.

## First run

There is nothing to download. Open the app, go to the **Source** stage, and
press *Generate a demo project* and *Generate demo media*. Both are made
locally, the media by the engine from ffmpeg's own test sources, so a first
run needs no network. `./al demo` fetches the original sample footage from a
cloud bucket if you want it.

`ALFRED_DEV_SKIP_AUTH=1 ./al dev` serves every request as a fixed superuser
and skips the login screen. It refuses to start alongside `ALFRED_PRODUCTION`
and prints a banner on every boot; see [docs/dev-auth.md](docs/dev-auth.md).

## Tests

```sh
./al pytest                       # API suite, plus black and ruff, in Docker
./al test                         # browser suite, in Docker, on a stack it builds
```

[CONTRIBUTING.md](CONTRIBUTING.md#running-the-tests) covers running either on
the host. Strategy and known gaps: [tests/README.md](tests/README.md) for the
backend, [website/e2e/README.md](website/e2e/README.md) for the browser suite.
Both deliberately list what is *not* covered.

The end-to-end suite is also the cookbook: `./al cookbook` generates
[docs/cookbook.md](docs/cookbook.md) from it, so every recipe in the docs is a
test that runs. The details are in
[CONTRIBUTING.md](CONTRIBUTING.md#the-docs-are-generated-from-the-tests).

## Documentation

Built with [mkdocs](https://www.mkdocs.org/):

```sh
./al docs                         # serves on :4000
```

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers the workflow, what CI checks, and the
two rules that are easy to break by accident: everything arrives as a pull
request, and contributor fields name humans.

## Versioning

`alfred/_version.py` is the source of truth; `website/package.json` tracks it.
See [CHANGELOG.md](CHANGELOG.md).
