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
| `./al demo` | Download demo media into `videos/` |
| `./al pytest` | API test suite, in Docker |
| `./al test` | End-to-end suite (Playwright), in Docker |
| `./al nox -s lint` | Ruff |
| `./al nox -s blacken` | Black (`-S`) |
| `./al docs` | Serve the docs locally on :4000 |
| `./al prod` | Production stack; expects a running traefik |
| `./al install <pkg>` | Add a website dependency |

`./al dev` publishes MongoDB on 27017. If something already holds that port
the stack will not start — see the dev-server notes in [AGENTS.md](AGENTS.md).

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

## Documentation

Built with [mkdocs](https://www.mkdocs.org/):

```sh
./al docs                         # serves on :4000
```

## Versioning

`alfred/_version.py` is the source of truth; `website/package.json` tracks it.
See [CHANGELOG.md](CHANGELOG.md).
