#!/bin/sh
# Read from alfred/_version.py, the source of truth, rather than restated
# here: the copy that used to sit on this line said v0.1.3 two releases after
# 0.1.3.
VERSION=v$(sed -n "s/^__version__ = ['\"]\(.*\)['\"]$/\1/p" "$(dirname "$0")/alfred/_version.py")

# Every command below, under every name it answers to, and nothing else:
# tests/unit/test_task_runner.py holds this list to the commands the script
# dispatches. It listed an `s` that did nothing, and left out six commands
# that worked (demo, thin, stop, seed, docs, pytest) and names others answer to.
HELP="./al

Init script and helper functions for Alfred

USAGE:
./al COMMAND [args]


COMMANDS:
init                    build the site's image; give this checkout a dev signing key
d | dev                 run the dev stack (--build rebuilds the images first)
thin                    run the dev stack without the render worker
stop                    stop the dev stack
reload                  rebuild and restart the dev stack's api
b | build               build the dev stack's images
docker | dock           docker compose with the dev stack's files: ./al docker ps
l | logs | log          follow the logs (docker compose logs -f)
sh                      a shell in the dev stack's api container
seed | db               put the demo projects in an empty database
reinit | reseed         drop every project and seed the demo ones again
storage                 tidy renders, deliveries and fetched media (--apply to act)
dump                    write the database to alfred_db_<date>.gz
restore                 load an archive written by dump: ./al restore FILE
demo | download | samples  download demo media into videos/ (needs the network)
t | test | e2e          the browser suite, in Docker (test_e2e.yml)
pt | pytest | py        the API suite, in Docker (pytest.yml)
loop                    suites side by side, one named run of several: ./al loop NAME --stack --keep
n | nox                 a nox session in the test container: ./al nox -s lint
cookbook                regenerate docs/cookbook.md from the browser specs
family                  alfred with otto, vox, joe, qmcp and the rest: status, test, up, smoke, down, loop
recipes                 record the recipes as GIFs, take the docs' screenshots (needs a dev stack)
docs | doc              serve the docs on http://127.0.0.1:4000
flower                  Celery monitoring on http://127.0.0.1:5555
i | install             add a frontend dependency: ./al install PACKAGE
w | worker              a render worker on this machine: ./al worker DB_HOST
p | prod | production   the production stack (export ALFRED_SECRET_KEY first)
r | restart             restart the production stack
g | git                 pull, then update the submodules
v | version | -v        print the version
"

# Returns a greeting quote to the user.
echo
shuf -n 1 quotes.csv
echo

downloadMedia() {
  echo "downloading demo media"
  mkdir -p videos && cd videos
  wget -N https://storage.googleapis.com/tower-bucket/moon.mp4
  wget -N https://storage.googleapis.com/tower-bucket/train.mp4
  wget -N https://storage.googleapis.com/tower-bucket/ATripToTheMoon-300k.mp4
  wget -N https://storage.googleapis.com/tower-bucket/TheGreatTrainRobbery-300k.mp4
  cd ..
}

# Say so when the dev stack is about to be reachable from other machines with
# its authentication switched off.
#
# dev.yml publishes on loopback unless ALFRED_BIND says otherwise, and
# ALFRED_BIND=0.0.0.0 is the documented way to try the app from a phone. With
# ALFRED_DEV_SKIP_AUTH on as well, every request is served as a superuser, so
# the combination hands the app to anyone on the network. A warning rather
# than a refusal: on a network you trust it may be exactly what you want.
warnIfExposed() {
  case "${ALFRED_BIND:-127.0.0.1}" in
    127.0.0.1 | localhost | ::1) return ;;
  esac
  skip=$(printf '%s' "${ALFRED_DEV_SKIP_AUTH:-}" | tr '[:upper:]' '[:lower:]' | tr -d ' ')
  case "$skip" in
    1 | true | yes | on)
      echo >&2
      echo "  ALFRED_BIND=$ALFRED_BIND publishes the dev stack beyond this machine," >&2
      echo "  and ALFRED_DEV_SKIP_AUTH is on: anyone who can reach it is served" >&2
      echo "  as a superuser. Use one or the other unless you trust the network." >&2
      echo >&2
      ;;
  esac
}

# A signing key of this checkout's own, for development.
#
# `.secret_key` is a committed stub with an empty key: PyJWT refuses it, so no
# login works, and signed media links die on each restart. dev.yml loads
# `.secret_key.local` over it; this creates it once, random and git-ignored.
# Delete it to rotate.
ensureDevKey() {
  key_file="$(dirname "$0")/.secret_key.local"
  [ -s "$key_file" ] && return
  key=$(od -An -N32 -tx1 /dev/urandom | tr -d ' 
')
  if [ ${#key} -ne 64 ]; then
    echo "  Could not generate a development signing key; the api keeps the empty stub key, and its tokens can be forged." >&2
    return
  fi
  (umask 077 && printf 'ALFRED_SECRET_KEY=%s
' "$key" > "$key_file")
  echo "  Created .secret_key.local, this checkout's own development signing key." >&2
}

# The compose project this checkout's stacks run as: COMPOSE_PROJECT_NAME, or
# what compose makes of the directory's name.
projectName() {
  if [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
    printf '%s\n' "$COMPOSE_PROJECT_NAME"
  else
    basename "$(cd "$(dirname "$0")" && pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-'
  fi
}

# Image prefix, per checkout, so worktrees never share images.
imagePrefix() {
  if [ -n "${ALFRED_IMAGES:-}" ]; then
    printf '%s\n' "$ALFRED_IMAGES"
  else
    basename "$(cd "$(dirname "$0")" && pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-'
  fi
}
ALFRED_IMAGES=$(imagePrefix)
export ALFRED_IMAGES

# A Python 3.8 or newer on this machine, for the scripts that run on the host
# and need nothing but its standard library. Each name is asked to run rather
# than merely found: on Windows `python3` can be the Store's stand-in, which
# is on PATH and runs nothing.
hostPython() {
  for candidate in python3 python; do
    if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  echo "./al: no Python 3.8 or newer on PATH (python3 or python)" >&2
  return 1
}

# Connect to a port on this machine; the exit status says what is there.
#
# curl, because a POSIX shell has no sockets of its own. 7 is a refused
# connection: nothing is listening. 0 is an HTTP answer. Anything else -- an
# empty reply, a reset, a timeout -- is a listener that does not speak HTTP,
# as MongoDB and the site's live-reload server need not. Five seconds to
# connect, because Windows takes about two to refuse a connection on loopback.
probePort() {
  curl -s -o /dev/null --connect-timeout 5 --max-time 6 "http://localhost:$1/" 2>/dev/null
}

# The container publishing a port, as "name project", when a container is.
publisher() {
  docker ps --filter "publish=$1" --format '{{.Names}} {{.Label "com.docker.compose.project"}}' 2>/dev/null | head -1
}

# Refuse to start on a port somebody else already holds.
#
# Docker publishes the port, but if another process bound it first the host
# port answers *them* -- so the stack looks healthy, the container serves
# correctly on its own network, and every request from the host reaches a
# different application. That happened here: another QM project defaults to
# 8000 too, and `curl localhost:8000` answered "Apothecary API" for an
# entire session while this stack was up and fine.
#
# The stack publishes three ports, and only the api's was checked. A held
# database or live-reload port failed the start with "port is already
# allocated", naming the port but neither the setting that moves it nor what
# holds it. All three are probed now, at once, and whatever is in the way is
# reported together, with one command that starts clear of it. A port this
# checkout's own stack holds is left to compose, which keeps or recreates its
# containers rather than colliding with them.
#
# Failing here with the occupant named beats discovering it later, or worse,
# not discovering it. Override rather than kill: ALFRED_PORT=8100 ./al dev
refuseTakenPorts() {
  run="./al $1"
  ALFRED_PORT="${ALFRED_PORT:-8000}"
  ALFRED_HMR_PORT="${ALFRED_HMR_PORT:-8001}"
  ALFRED_DB_PORT="${ALFRED_DB_PORT:-27017}"
  # Without curl there is no probe, and the stack starts unguarded, as it did
  # before there was a guard.
  command -v curl >/dev/null 2>&1 || return 0

  probePort "$ALFRED_PORT" & api=$!
  probePort "$ALFRED_HMR_PORT" & hmr=$!
  probePort "$ALFRED_DB_PORT" & db=$!
  wait $api; api_status=$?
  wait $hmr; hmr_status=$?
  wait $db; db_status=$?

  project=$(projectName)
  moves=""

  if [ $api_status -ne 7 ]; then
    holder=$(publisher "$ALFRED_PORT")
    if [ -n "$holder" ] && [ "${holder#* }" = "$project" ]; then
      if [ $api_status -eq 0 ]; then
        echo >&2
        echo "  Alfred is already running from this checkout, on port $ALFRED_PORT." >&2
        echo >&2
        echo "  Stop it first:  ./al stop" >&2
        echo >&2
        exit 1
      fi
      # This checkout's api, not answering yet: compose will recreate it.
    else
      occupant=""
      if [ $api_status -eq 0 ]; then
        # First match, not last: an OpenAPI document has a `title` per schema
        # as well as the one in `info`, and a greedy pattern finds the wrong one.
        occupant=$(curl -s --max-time 3 "http://localhost:$ALFRED_PORT/openapi.json" 2>/dev/null | head -c 400 | grep -o '"title":"[^"]*"' | head -1 | cut -d'"' -f4)
      fi
      echo >&2
      if [ "$occupant" = "Alfred API" ]; then
        echo "  Port $ALFRED_PORT (ALFRED_PORT) is held by another Alfred stack${holder:+, the container ${holder%% *}}." >&2
      elif [ $api_status -eq 0 ]; then
        echo "  Port $ALFRED_PORT (ALFRED_PORT) is already answering, and not as Alfred." >&2
        echo "  Starting here would look fine and be wrong: the container would" >&2
        echo "  serve correctly on its own network while every request from your" >&2
        echo "  machine reached whatever holds the port." >&2
        echo "  It identifies itself as:  ${occupant:-(no OpenAPI document)}" >&2
      else
        echo "  Port $ALFRED_PORT (ALFRED_PORT) is already in use, by something that does" >&2
        echo "  not answer HTTP${holder:+: the container ${holder%% *}}." >&2
      fi
      moves="$moves ALFRED_PORT=$((ALFRED_PORT + 100))"
    fi
  fi

  if [ $hmr_status -ne 7 ]; then
    holder=$(publisher "$ALFRED_HMR_PORT")
    if [ -z "$holder" ] || [ "${holder#* }" != "$project" ]; then
      echo >&2
      echo "  Port $ALFRED_HMR_PORT (ALFRED_HMR_PORT, the site's live reload) is already" >&2
      echo "  in use${holder:+, by the container ${holder%% *}}." >&2
      moves="$moves ALFRED_HMR_PORT=$((ALFRED_HMR_PORT + 100))"
    fi
  fi

  if [ $db_status -ne 7 ]; then
    holder=$(publisher "$ALFRED_DB_PORT")
    if [ -z "$holder" ] || [ "${holder#* }" != "$project" ]; then
      echo >&2
      echo "  Port $ALFRED_DB_PORT (ALFRED_DB_PORT, the database) is already in use," >&2
      if [ -n "$holder" ]; then
        echo "  by the container ${holder%% *}." >&2
      else
        echo "  most likely by a standalone mongod or another project's database." >&2
      fi
      moves="$moves ALFRED_DB_PORT=$((ALFRED_DB_PORT + 100))"
    fi
  fi

  if [ -n "$moves" ]; then
    echo >&2
    echo "  Start elsewhere instead:  ${moves# } $run" >&2
    echo >&2
    exit 1
  fi
}

if [ -z $1 ]; then
  echo "$HELP"

elif [ $1 = "version" -o $1 = "v" -o $1 = "-v" ]; then
  echo $VERSION

elif [ $1 = "b" -o $1 = "build" ]; then
  echo "Building docker image"
  shift
  docker compose -f docker-compose.yml -f dev.yml build "$@"

# Starts in development (optional "--build")
elif [ $1 = "d" ] || [ $1 = "dev" ]; then
  if [ !-z ]; then shift; fi
  ensureDevKey
  refuseTakenPorts dev
  warnIfExposed
  echo "Alfred! running dev $1  (http://127.0.0.1:$ALFRED_PORT)"
  ALFRED_PORT="$ALFRED_PORT" docker compose -f docker-compose.yml -f dev.yml up "$@"

# Starts in production.
elif [ $1 = "p" -o $1 = "production" -o $1 = "prod" ]; then
  shift
  # Before anything stops: production.yml refuses to start without the
  # production signing key, and this takes the running stack down first, so
  # a missing key found at `up` would leave production down.
  if [ -z "${ALFRED_SECRET_KEY:-}" ]; then
    echo "ALFRED_SECRET_KEY is not set. Production signs session tokens with its" >&2
    echo "own key; export it, then run ./al prod again. Nothing was stopped." >&2
    exit 1
  fi
  echo "Alfred! running production $1"
  # The docs, with the Material release pdm.docs.lock holds for `./al docs`
  # (pyproject.toml's docs group). Unpinned, it built production's docs with
  # whatever `latest` meant on the day: 9.8.0 was a day old as this was pinned.
  docker compose down && \
  docker run --rm -it -v ${PWD}:/docs -v ${PWD}/alfred/site/:/site/ --user $(id -u):$(id -g) squidfunk/mkdocs-material:9.7.7 build -d /site/ && \
  docker compose -f docker-compose.yml -f production.yml up --build -d $1

# Installs website dependencies.
elif [ $1 = "init" ]; then
  shift
  ensureDevKey
  mkdir -p $(dirname $0)/website/dist
  # The media library the stack mounts at /app/videos. Created here so a
  # Linux host owns it, rather than the root-owned directory Docker would
  # make. (This used to create alfred/videos, alfred/data and alfred/site,
  # which nothing mounts; the /data mount is gone altogether.)
  mkdir -p $(dirname $0)/videos
  echo "installing dependencies"
  # Dependencies live in the image, not in the host's website/node_modules, so
  # this builds rather than installing into the bind mount. --renew-anon-volumes
  # is what actually picks up a dependency change: the anonymous volume holding
  # /app/node_modules survives an ordinary `up`, so without it a rebuilt image
  # still serves the previous install.
  docker compose build website
  docker compose up --no-start --renew-anon-volumes website

  # Installs the dependencies.
elif [ $1 = "i" -o $1 = "install" ]; then
    shift
    echo "installing dependencies"
    # make install
    docker compose -f docker-compose.yml run website yarn add "$@"

elif [ $1 = "recipes" ]; then
  shift
  # The docs' pictures, from the `docs` Playwright project:
  #   1. record the @recipe walkthroughs, and take the @screens into
  #      docs/assets/screens/;
  #   2. copy each passing recipe's recording into docs/recipes/ (git-ignored);
  #   3. turn each into docs/recipes/<recipe>.gif, with ffmpeg in the dev
  #      stack's api container (scripts/recipe_gifs.py);
  #   4. regenerate the cookbook.
  # docs/recipes/ is git-ignored: the recordings play in the cookbook of the
  # docs served locally (`./al docs`), and are not committed.
  # Needs the dev stack up: E2E_BASE_URL if it is not on :8000, and
  # COMPOSE_PROJECT_NAME if it runs under another name. Every step runs, so a
  # recipe that fails loses its GIF rather than keeping a stale one; the
  # collector leaves docs/recipes alone if the run reached no recipe. Exits 1,
  # naming the steps that failed.
  cd "$(dirname "$0")"
  failed=""
  (cd website && npx playwright test --project=docs --reporter=json > recipe-report.json) ||
    failed="$failed record"
  node website/e2e/collect-recipe-videos.js || failed="$failed collect"
  docker compose -f docker-compose.yml -f dev.yml exec -T api python scripts/recipe_gifs.py ||
    failed="$failed convert"
  node website/e2e/cookbook.js || failed="$failed cookbook"
  if [ -n "$failed" ]; then
    echo "./al recipes failed:$failed" >&2
    exit 1
  fi

elif [ $1 = "cookbook" ]; then
  shift
  # Regenerate docs/cookbook.md from the end-to-end specs. The tests are the
  # source; the prose is a build artefact. tests/unit/test_cookbook.py fails if
  # the committed file drifts from them.
  node website/e2e/cookbook.js "$@"

elif [ $1 = "family" ]; then
  shift
  # alfred and the repositories it works with, on this machine
  # (scripts/family.py, docs/family.md):
  #   ./al family                status of each, and the vendored pins
  #   ./al family test [NAME]    each one's quick suite (--full: the whole)
  #   ./al family up [--build]   joe, then the dev stack pointed at it
  #   ./al family smoke          a live check of the running stack
  #   ./al family down           the dev stack, and the joe `up` started
  #   ./al family loop           test, up, smoke, down (--keep: stay up)
  py=$(hostPython) || exit 1
  "$py" "$(dirname "$0")/scripts/family.py" "$@"

elif [ $1 = "flower" ]; then
  shift
  # Celery monitoring on http://localhost:5555. Needs the dev stack up for the
  # broker; flower.yml only brings up flower itself. On loopback unless
  # ALFRED_BIND says otherwise, like the dev stack (flower.yml says why).
  docker compose -f flower.yml up "$@"

elif [ $1 = "demo" -o $1 = "download" -o $1 = "samples" ]; then
  shift
  downloadMedia

# Starts development without the renderer
elif [ $1 = "thin" ]; then
  shift
  ensureDevKey
  # The same three ports as `./al dev`, so the same guard.
  refuseTakenPorts thin
  warnIfExposed
  echo "Alfred! thin dev stack, no renderer  (http://127.0.0.1:$ALFRED_PORT)"
  ALFRED_PORT="$ALFRED_PORT" docker compose     -f docker-compose.yml -f dev.yml -f thin.yml up "$@"

# Stops the dev stack
elif [ $1 = "stop" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml down "$@"

elif [ $1 = "restart" -o $1 = "r" ]; then
  shift
  docker compose -f docker-compose.yml -f production.yml restart

elif [ $1 = "seed" -o $1 = "db" ]; then
  shift
  # What the api does at startup, on request: the demo projects go into an
  # empty Project collection, and one with anything in it is left alone.
  #
  # Both of these called python3.10, which the image does not have, and
  # imported `seed` and `db` as top-level modules, which they are not; seed
  # also wrote to `projects`, a collection nothing reads. They run the api
  # image's own interpreter against the modules the api uses.
  # Owned the way startup seeding owns them (ALFRED_SEED_OWNER; in
  # development, the dev user), so a seeded project is visible to the same
  # account whichever path put it there.
  docker compose exec api python -c '
from alfred.config import SEED_OWNER
from alfred.core.utils import get_sync_db
from alfred.seed import owned_by, seed

db = get_sync_db()
if db.Project.count_documents({}):
    print("Project already holds documents; nothing seeded. ./al reseed replaces them.")
else:
    db.Project.insert_many(owned_by(SEED_OWNER, seed))
    print(f"seeded {len(seed)} projects, owner: {SEED_OWNER}")
'

elif [ $1 = "reinit" -o $1 = "reseed" ]; then
  shift
  # Drops the Project collection and seeds it again -- destructive on purpose.
  docker compose exec api python -c '
from alfred.config import SEED_OWNER
from alfred.core.utils import get_sync_db
from alfred.seed import owned_by, seed

db = get_sync_db()
db.Project.drop()
db.Project.insert_many(owned_by(SEED_OWNER, seed))
print(f"dropped Project and seeded {len(seed)} projects, owner: {SEED_OWNER}")
'

elif [ $1 = "sh" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml exec api sh "$@"

elif [ $1 = "storage" ]; then
  shift
  # Tidy what the server keeps on disk, from inside the running api, which
  # sees the same directories and database the server does. Dry runs unless
  # told --apply.
  #
  #   ./al storage migrate             render outputs still in the media
  #                                    library: what would move to the render
  #                                    directory, and what is in the way
  #   ./al storage migrate --apply     move them
  #   ./al storage orphans [--apply]   files whose render has been deleted
  #   ./al storage cache [--apply]     remote media the engine fetched, past
  #                                    ALFRED_REMOTE_CACHE_TTL (--all: every one)
  #
  # -T: no terminal, so this works from scripts and CI as well as a shell.
  docker compose exec -T api python -m alfred.core.utils.storage "$@"

elif [ $1 = "l" -o $1 = "logs" -o $1 = "log" ]; then
  shift
  docker compose logs -f "$@"

elif [ $1 = "w" -o $1 = "worker" ]; then
  shift
  # . operator used in place of source
  . ./.cred
  # DB_URL=mongodb://$1:27017 CELERY_BROKER=$DB_URL/celery CELERY_BACKEND=$CELERY_BROKER celery -A tasks:renderer --workdir alfred/ -b $CELERY_BROKER --result-backend $CELERY_BACKEND worker --concurrency=4
  DB_URL=mongodb://$1:27017 DB_NAME=alfred CELERY_BROKER=$DB_URL/celery CELERY_BACKEND=$CELERY_BROKER celery -A alfred.core.utils:renderer --workdir alfred/ worker --concurrency=4
  # docker compose -f docker-compose.yml -f dev.yml run -it --entrypoint "celery -A alfred.core.utils.tasks:renderer --workdir /app/alfred -b mongodb://$1:27017/celery --result-backend mongodb://$1:27017/celery worker --loglevel=debug --concurrency=1" renderer

elif [ $1 = "dump" ]; then
  shift
  DATE=`date "+%Y-%m-%d-%H%M%S"`
  FILENAME=alfred_db_$DATE.gz
  # Streamed out of the db service, rather than written inside the container
  # and copied out by name: `alfred_db_1` is how compose v1 named it, compose
  # v2 says `alfred-db-1`, so the copy found no container and the dump stayed
  # inside one. -T because a TTY would mangle the archive's bytes.
  if docker compose exec -T db mongodump --db alfred --gzip --archive > "$FILENAME"; then
    echo "wrote $FILENAME"
  else
    rm -f "$FILENAME"
    echo "dump failed; is the stack running?" >&2
    exit 1
  fi

elif [ $1 = "restore" ]; then
  shift
  if [ ! -f "$1" ]; then
    echo "usage: ./al restore <archive written by ./al dump>" >&2
    exit 1
  fi
  # Streamed in, for the same reason dump streams out. --drop replaces each
  # collection the archive holds with the archive's copy.
  docker compose exec -T db mongorestore --gzip --archive --drop < "$1"

elif [ $1 = "reload" ]; then
  shift
  # reload otto
  docker compose -f docker-compose.yml -f dev.yml up -d --build api

elif [ $1 = "g" -o $1 = "git" ]; then
  shift
  git pull && git submodule update

elif [ $1 = "docs" -o $1 = "doc" ]; then
  # Build the documentation and serve it, reloading as it changes, on
  # http://localhost:4000. Loopback unless ALFRED_BIND says otherwise, like the
  # dev stack: on 0.0.0.0 it served this checkout's docs -- drafts included --
  # to the whole network by default. ALFRED_BIND=0.0.0.0 ./al docs opens it.
  shift
  mkdocs serve -a "${ALFRED_BIND:-127.0.0.1}:4000"

elif [ $1 = "docker" -o $1 = "dock" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml "$@"

elif [ $1 = "t" -o $1 = "test" -o $1 = "e2e" ]; then
  shift
  # A compose project of its own. test_e2e.yml names its services api,
  # renderer and db, as the dev stack does, and under the checkout's default
  # project they were the dev stack's containers: a run recreated a running
  # dev stack with the test configuration. As <project>-e2e the two never meet.
  e2e="docker compose -p $(projectName)-e2e -f test_e2e.yml"
  # From nothing, as CI starts. `down --volumes` removes what the last run
  # left: its containers, the volume its renders and deliveries are on, and
  # the anonymous volumes holding the database and the node_modules of the
  # site and the runner. --renew-anon-volumes alone gave each run fresh ones
  # and left the old ones behind, unused, a set per run. The last run's
  # containers and volumes stay until the next one, for its logs and outputs:
  #   docker compose -p <project>-e2e -f test_e2e.yml logs api
  $e2e down --volumes --remove-orphans
  # --build, as CI runs it, so a local run tests this checkout's images rather
  # than whichever ones an earlier run left behind. --renew-anon-volumes for
  # the same reason, should `down` have left a container: the site's
  # node_modules and the database are anonymous volumes, and compose hands a
  # recreated container its old ones -- so after a dependency change the
  # bundle was built against the previous install.
  $e2e up --build --renew-anon-volumes --exit-code-from e2e "$@"

elif [ $1 = "pt" -o $1 = "pytest" -o $1 = "py" ]; then
  shift
  # A compose project of its own, as `./al test` has. pytest.yml's throwaway
  # database is a service named `db`, as the dev stack's is, so under the
  # checkout's own project a run recreated a running dev stack's database
  # container with the test's -- and the api went on talking to it.
  # --build: the image holds the dependencies.
  docker compose -p "$(projectName)-pytest" -f pytest.yml up --build --exit-code-from pytest "$@"

elif [ $1 = "loop" ]; then
  shift
  # Suites side by side, as named runs. See docs/loop.md.
  py=$(hostPython) || exit 1
  "$py" "$(dirname "$0")/scripts/loop.py" "$@"

elif [ $1 = "n" -o $1 = "nox" ]; then
  shift
  # In the container, like every other command here. This ran `nox` on the
  # host, which is not a documented prerequisite and is not installed by
  # `./al init` -- so `./al nox -s lint`, which AGENTS.md and CONTRIBUTING.md
  # both name as the pre-pull-request gate, failed with `nox: command not
  # found` for anyone who followed the instructions.
  docker compose -p "$(projectName)-pytest" -f pytest.yml run --rm pytest -f tests/noxfile.py "$@"

else
  echo "Unknown command: $1"
  echo "Error when running $@"
  echo "$HELP"

fi
