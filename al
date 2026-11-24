#!/bin/sh
# From alfred/_version.py, never restated here.
VERSION=v$(sed -n "s/^__version__ = ['\"]\(.*\)['\"]$/\1/p" "$(dirname "$0")/alfred/_version.py")

# Every command, under every name it answers to, and nothing else:
# tests/unit/test_task_runner.py holds this list to the dispatch below.
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

# A greeting.
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

# Warn, not refuse, when ALFRED_BIND leaves loopback with the auth bypass on:
# anyone on the network is then a superuser. See docs/dev-server.md.
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

# This checkout's dev signing key, .secret_key.local: made once, random,
# git-ignored, loaded over the empty stub. Delete it to rotate.
# See docs/configuration.md#the-signing-key.
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

# A host Python >= 3.8 for the stdlib-only scripts. Run, not just found:
# Windows' `python3` can be the Store stub, which runs nothing.
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

# curl's exit status says what holds a port: 7 nothing, 0 HTTP, anything
# else a listener that is not HTTP (MongoDB). 5 s: Windows is slow to refuse.
probePort() {
  curl -s -o /dev/null --connect-timeout 5 --max-time 6 "http://localhost:$1/" 2>/dev/null
}

# The container publishing a port, as "name project", when a container is.
publisher() {
  docker ps --filter "publish=$1" --format '{{.Names}} {{.Label "com.docker.compose.project"}}' 2>/dev/null | head -1
}

# Refuse to start on any of the three ports someone else holds, naming the
# holder and one command that moves clear of all of them. Ports this
# checkout's own stack holds are left to compose. See docs/dev-server.md.
refuseTakenPorts() {
  run="./al $1"
  ALFRED_PORT="${ALFRED_PORT:-1732}"
  ALFRED_HMR_PORT="${ALFRED_HMR_PORT:-1733}"
  ALFRED_DB_PORT="${ALFRED_DB_PORT:-27017}"
  # No curl, no probe: start unguarded.
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
        # The first title is info's; every schema has one too.
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
  # Before anything stops: found missing at `up`, production would stay down.
  if [ -z "${ALFRED_SECRET_KEY:-}" ]; then
    echo "ALFRED_SECRET_KEY is not set. Production signs session tokens with its" >&2
    echo "own key; export it, then run ./al prod again. Nothing was stopped." >&2
    exit 1
  fi
  echo "Alfred! running production $1"
  # Material at the release pdm.docs.lock holds; test_docs_site.py checks.
  docker compose down && \
  docker run --rm -it -v ${PWD}:/docs -v ${PWD}/alfred/site/:/site/ --user $(id -u):$(id -g) squidfunk/mkdocs-material:9.7.7 build -d /site/ && \
  docker compose -f docker-compose.yml -f production.yml up --build -d $1

# The site's image, this checkout's dev key, and videos/.
elif [ $1 = "init" ]; then
  shift
  ensureDevKey
  mkdir -p $(dirname $0)/website/dist
  # The library the stacks mount at /app/videos; made here so a Linux host
  # owns it, not root.
  mkdir -p $(dirname $0)/videos
  echo "installing dependencies"
  # The image holds the site's dependencies. --renew-anon-volumes: the old
  # node_modules volume survives a plain `up`. See docs/dev-server.md.
  docker compose build website
  docker compose up --no-start --renew-anon-volumes website

# Adds a frontend dependency.
elif [ $1 = "i" -o $1 = "install" ]; then
    shift
    echo "installing dependencies"
    docker compose -f docker-compose.yml run website yarn add "$@"

elif [ $1 = "recipes" ]; then
  shift
  # Record, collect, convert, regenerate. Every step runs; a failed one is
  # named. Needs the dev stack up (E2E_BASE_URL, COMPOSE_PROJECT_NAME).
  # See CONTRIBUTING.md#the-docs-are-generated-from-the-tests.
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
  # docs/cookbook.md from the specs; test_cookbook.py fails on drift.
  node website/e2e/cookbook.js "$@"

elif [ $1 = "family" ]; then
  shift
  # See docs/family.md.
  py=$(hostPython) || exit 1
  "$py" "$(dirname "$0")/scripts/family.py" "$@"

elif [ $1 = "flower" ]; then
  shift
  # http://127.0.0.1:5555; needs the dev stack's broker up.
  docker compose -f flower.yml up "$@"

elif [ $1 = "demo" -o $1 = "download" -o $1 = "samples" ]; then
  shift
  downloadMedia

# Starts development without the renderer
elif [ $1 = "thin" ]; then
  shift
  ensureDevKey
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
  # Startup's seeding, on request: only into an empty Project collection,
  # owned by ALFRED_SEED_OWNER as at startup.
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
  # Destructive: drops Project, then seeds it.
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
  # In the running api; a dry run unless --apply. ./al storage --help.
  # -T: no TTY, so scripts can call it.
  docker compose exec -T api python -m alfred.core.utils.storage "$@"

elif [ $1 = "l" -o $1 = "logs" -o $1 = "log" ]; then
  shift
  docker compose logs -f "$@"

elif [ $1 = "w" -o $1 = "worker" ]; then
  shift
  . ./.cred
  DB_URL=mongodb://$1:27017 DB_NAME=alfred CELERY_BROKER=$DB_URL/celery CELERY_BACKEND=$CELERY_BROKER celery -A alfred.core.utils:renderer --workdir alfred/ worker --concurrency=4

elif [ $1 = "dump" ]; then
  shift
  DATE=`date "+%Y-%m-%d-%H%M%S"`
  FILENAME=alfred_db_$DATE.gz
  # Streamed out, not copied by container name. -T: a TTY mangles the bytes.
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
  # --drop: each collection in the archive replaces the database's.
  docker compose exec -T db mongorestore --gzip --archive --drop < "$1"

elif [ $1 = "reload" ]; then
  shift
  # Rebuild and restart the api.
  docker compose -f docker-compose.yml -f dev.yml up -d --build api

elif [ $1 = "g" -o $1 = "git" ]; then
  shift
  git pull && git submodule update

elif [ $1 = "docs" -o $1 = "doc" ]; then
  # http://127.0.0.1:4000, live; ALFRED_BIND=0.0.0.0 serves the network.
  shift
  mkdocs serve -a "${ALFRED_BIND:-127.0.0.1}:4000"

elif [ $1 = "docker" -o $1 = "dock" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml "$@"

elif [ $1 = "t" -o $1 = "test" -o $1 = "e2e" ]; then
  shift
  # <project>-e2e: its service names are the dev stack's. See docs/build.md.
  e2e="docker compose -p $(projectName)-e2e -f test_e2e.yml"
  # From nothing, as CI. The last run stays until now, for its logs.
  $e2e down --volumes --remove-orphans
  # This checkout's images and dependencies, never an earlier run's.
  $e2e up --build --renew-anon-volumes --exit-code-from e2e "$@"

elif [ $1 = "pt" -o $1 = "pytest" -o $1 = "py" ]; then
  shift
  # <project>-pytest: its `db` would replace the dev stack's. --build: the
  # image holds the dependencies.
  docker compose -p "$(projectName)-pytest" -f pytest.yml up --build --exit-code-from pytest "$@"

elif [ $1 = "loop" ]; then
  shift
  # See docs/loop.md.
  py=$(hostPython) || exit 1
  "$py" "$(dirname "$0")/scripts/loop.py" "$@"

elif [ $1 = "n" -o $1 = "nox" ]; then
  shift
  # In the test container, under <project>-pytest: the host needs no nox.
  docker compose -p "$(projectName)-pytest" -f pytest.yml run --rm pytest -f tests/noxfile.py "$@"

else
  echo "Unknown command: $1"
  echo "Error when running $@"
  echo "$HELP"

fi
