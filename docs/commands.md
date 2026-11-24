# Commands on each system

Everything runs through `./al`, a `sh` script at the root of the repository. On
Linux, macOS, Git Bash and WSL it is run as it is; in PowerShell, through Git's
bash, by the `al` function below. What differs between systems is the setup,
how an environment variable is set for one command, and a few things that bite
on one system only.

## Set up once

=== "Linux"

    ```sh
    # Docker Engine with the Compose plugin: https://docs.docker.com/engine/install/
    sudo apt install git python3 nodejs npm      # or your distribution's names
    curl -LsSf https://astral.sh/uv/install.sh | sh
    sudo npm install -g yarn
    ```

=== "macOS"

    ```sh
    brew install --cask docker                   # Docker Desktop
    brew install git python node uv yarn
    ```

=== "Windows"

    ```powershell
    winget install Docker.DockerDesktop
    winget install Git.Git
    winget install Python.Python.3.12
    winget install OpenJS.NodeJS.LTS
    winget install astral-sh.uv
    npm install -g yarn
    ```

    Then, in PowerShell, `al` runs `./al` through Git's own bash. Add it to
    `$PROFILE` to keep it:

    ```powershell
    function al { & ((Split-Path (Split-Path (Get-Command git).Source)) + '\bin\bash.exe') ./al @args }
    ```

    Not the `bash` PowerShell finds on its own: on a machine with WSL that is
    `C:\Windows\System32\bash.exe`, which runs the script inside Linux instead.
    Git Bash needs neither: `./al` runs there as on Linux.

Then, on every system, clone with the engines and install what the host runs:

```sh
git clone --recurse-submodules https://github.com/quaternionmedia/alfred.git
cd alfred
./al init                                            # the site's image, and this checkout's signing key
cd website && yarn install --frozen-lockfile && npx playwright install chromium && cd ..
```

The last line is only for what runs a browser on the host: the docs'
screenshots and the recipes' recordings. The suites run their own browsers in
Docker.

| What | Why |
|---|---|
| Docker with `docker compose` | the api, the render worker, the database, the site's build and both test suites run in containers |
| git | the engines, otto and vox, are submodules; the images do not build without them |
| Python 3.8 or newer | `./al family` and `./al loop` run on the host with its standard library |
| uv | joe, the docs build and the host's quick tests (`uv`, `uvx`) |
| Node.js and yarn | the host's browser, for screenshots and recordings |

## Run, test, look

Set up as above, the same command does the same thing everywhere. In bash, a
variable in front of a command is set for that command only; in PowerShell,
`$env:` sets it for the rest of the session, until `Remove-Item Env:NAME`.

| Task | Linux, macOS, Git Bash, WSL | PowerShell |
|---|---|---|
| Start the app | `./al dev` | `al dev` |
| ... in the background | `./al dev -d` | `al dev -d` |
| ... without logging in | `ALFRED_DEV_SKIP_AUTH=1 ./al dev` | `$env:ALFRED_DEV_SKIP_AUTH = '1'; al dev` |
| ... on another port | `ALFRED_PORT=8100 ./al dev` | `$env:ALFRED_PORT = '8100'; al dev` |
| ... with joe, for captions | `ALFRED_FAMILY_JOE=../joe ./al family up` | `$env:ALFRED_FAMILY_JOE = '../joe'; al family up` |
| Stop it | `./al stop` | `al stop` |
| ... and the joe it started | `./al family down` | `al family down` |
| Follow its logs | `./al logs` | `al logs` |
| A shell in the api | `./al sh` | `al sh` |
| After editing `alfred/`, on Windows and macOS | `./al docker restart api` | `al docker restart api` |
| Every suite, side by side | `./al loop` | `al loop` |
| ... then the app, left up to try | `./al loop --stack --keep` | `al loop --stack --keep` |
| A second run beside the first | `./al loop slow --only e2e --grep @slow` | `al loop slow --only e2e --grep @slow` |
| Take a run's stack down | `./al loop NAME --down` | `al loop NAME --down` |
| The API suite | `./al pytest` | `al pytest` |
| The browser suite | `./al test` | `al test` |
| Lint, then format | `./al nox -s lint`, `./al nox -s blacken` | `al nox -s lint`, `al nox -s blacken` |
| Screenshots and recordings | `./al loop shots --only recipes` | `al loop shots --only recipes` |
| Serve the docs | `uvx --with 'mkdocs-material>=9.7,<10' --from 'mkdocs>=1.6,<2' mkdocs serve -a 127.0.0.1:4000` | the same |
| Where every repository is | `./al family` | `al family` |
| Every command | `./al` | `al` |

[The test loop](loop.md) says what each run of `./al loop` starts, and [the
family dev loop](family.md) what `./al family` does with joe and the rest.
`./al docs` serves the docs too, with a `mkdocs` already on the host's
`PATH`.

## Where things answer

| What | Address |
|---|---|
| The editor | <http://127.0.0.1:8000> |
| The API's own reference | <http://127.0.0.1:8000/api> |
| The docs, served | <http://127.0.0.1:4000/docs/> |
| joe | <http://127.0.0.1:8010> |
| The database, for a GUI | `127.0.0.1:27017` |

`127.0.0.1` rather than `localhost`: everything is published on IPv4 loopback,
and on Windows a client that tries `localhost` asks IPv6 first and waits about
two seconds for each refusal.

## What bites on one system

| System | What | What to do |
|---|---|---|
| Windows, macOS | The api's `--reload` never sees an edit: file events do not cross Docker's bind mount. | `./al docker restart api` after editing `alfred/` ([dev-server notes](dev-server.md)). |
| Windows | `bash` in PowerShell can be WSL's. | Use the `al` function above, or Git Bash. |
| Windows | The instruction files are symlinks. | Optional: Developer Mode, then `git config core.symlinks true` and `git checkout -- .` (`AGENTS.md`). |
| Windows, WSL | Git for Windows checks text out with CRLF line endings, which Linux's `sh` reads as part of each command. | `.gitattributes` keeps `./al` and the shell scripts LF on every checkout. |
| Linux | The database container runs as `${UID}:${GID}`, which most shells do not export. | `export UID; export GID=$(id -g)` if it fails to start. |
| Linux | A container cannot reach the host's loopback, so joe on `127.0.0.1` is out of its reach. | `./al family up` puts joe on docker0's address ([Configuration](configuration.md#docker-hosts-and-joe)). |
