# alfred

> *"Drama is life with all the dull bits cut out."*
>
> ~ Alfred Hitchcock

Alfred is a video editor that works even without a server, designed for quick
editing from anywhere, including mobile devices.

Demo at [alfred.quaternion.media](https://alfred.quaternion.media)

## Shape

A small **control plane** (`alfred/`) orchestrating a **render engine**
(`otto`, published separately as `al-otto`). The control plane owns auth,
project and render lifecycle, and orchestration; it does not touch media.
`website/` is a mithril SPA built with parcel.

The project is governed by the [Quaternion Media
constitution](https://github.com/quaternionmedia/qm), vendored at
`governance/qm`. Start at [AGENTS.md](AGENTS.md) — it is the entry point for
contributors and coding agents alike, and it names the project's known
governance gaps.

## Clone

```sh
git clone --recurse-submodules git@github.com:quaternionmedia/alfred.git
cd alfred
./al init          # install website dependencies
```

Already cloned without submodules:

```sh
git submodule update --init --recursive
```

On Windows, `CLAUDE.md` and `.github/copilot-instructions.md` are symlinks;
see [AGENTS.md](AGENTS.md) for the one-time `core.symlinks` step.

## Common commands

Everything routes through `./al`. Run it with no arguments for the full list.

| Command | What it does |
|---|---|
| `./al init` | Install website dependencies |
| `./al dev` | Run the dev stack; app on http://localhost:8000 |
| `./al dev --build` | Rebuild images first |
| `./al demo` | Download demo media into `videos/` (needs network; the app can generate its own) |
| `./al pytest` | API test suite, in Docker |
| `./al test` | End-to-end suite (Playwright), in Docker |
| `./al nox -s lint` | Ruff |
| `./al nox -s blacken` | Black (`-S`) |
| `./al docs` | Serve the docs locally on :4000 |
| `./al prod` | Production stack; expects a running traefik |
| `./al flower` | Celery monitoring on :5555; needs the dev stack for its broker |
| `./al cookbook` | Regenerate `docs/cookbook.md` from the e2e specs |
| `./al install <pkg>` | Add a website dependency |

`./al dev` publishes MongoDB on 27017. If something already holds that port
the stack will not start — see the dev-server notes in [AGENTS.md](AGENTS.md).

## First run

There is nothing to download. Open the app, go to the **Source** stage, and
press *Generate a demo project* and *Generate demo media* — both are
synthesised locally with ffmpeg, so a first run needs no network access. `./al
demo` still fetches the original sample footage from a cloud bucket if you want
it.

To work without logging in, `ALFRED_DEV_SKIP_AUTH=1 ./al dev` serves every
request as a fixed superuser and skips the login screen. It refuses to start
alongside `ALFRED_PRODUCTION` and prints a banner on every boot — see
[docs/dev-auth.md](docs/dev-auth.md).

## Tests

```sh
pdm install                       # Python deps
pdm run pytest                    # unit + pipeline suite
pdm run pytest -m "not needs_ffmpeg and not needs_db"   # no external tools

cd website && npm install
npx playwright install chromium
npm run e2e                       # end-to-end, against a running ./al dev
```

Strategy and known gaps: [tests/README.md](tests/README.md) for the backend,
[website/e2e/README.md](website/e2e/README.md) for the browser suite. Both
list what is *not* covered, deliberately.

The end-to-end suite is also the cookbook: [docs/cookbook.md](docs/cookbook.md)
is generated from it by `./al cookbook`, so every recipe in the documentation
is a test that runs. Prose describing behaviour goes stale silently; a test
describing behaviour goes red.

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
