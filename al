#!/bin/sh
# Read from alfred/_version.py, the source of truth, rather than restated
# here: the copy that used to sit on this line said v0.1.3 two releases after
# 0.1.3.
VERSION=v$(sed -n "s/^__version__ = ['\"]\(.*\)['\"]$/\1/p" "$(dirname "$0")/alfred/_version.py")

HELP="./al

Init script and helper functions for Alfred

USAGE:
./al COMMAND [args]


COMMANDS:
b | build
cookbook
recipes
d | dev
docker | dock
flower
dump
git
i | install
init
l | log
n | nox
p | production
reload
r | restart
reseed
restore
s | sh
storage
t | test | e2e
v | version
w | worker
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
# docker-compose.yml loads `.secret_key`, a committed stub that sets
# ALFRED_SECRET_KEY to nothing. PyJWT signs with an empty key without
# complaint, so every development token could be forged by anyone who knew
# that, and the media links the api signs died with each restart because it
# fell back to a key of its own. dev.yml also loads `.secret_key.local`; this
# creates it once, with a random key, and git ignores it. Delete it to rotate.
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

  # Refuse to start on a port somebody else already holds.
  #
  # Docker publishes the port, but if another process bound it first the host
  # port answers *them* -- so the stack looks healthy, the container serves
  # correctly on its own network, and every request from the host reaches a
  # different application. That happened here: another QM project defaults to
  # 8000 too, and `curl localhost:8000` answered "Apothecary API" for an
  # entire session while this stack was up and fine.
  #
  # Failing here with the occupant named beats discovering it later, or worse,
  # not discovering it. Override rather than kill: ALFRED_PORT=8100 ./al dev
  ALFRED_PORT="${ALFRED_PORT:-8000}"
  if curl -s -o /dev/null --max-time 3 "http://localhost:$ALFRED_PORT/" 2>/dev/null; then
    # First match, not last: an OpenAPI document has a `title` per schema as
    # well as the one in `info`, and a greedy pattern finds the wrong one.
    occupant=$(curl -s --max-time 3 "http://localhost:$ALFRED_PORT/openapi.json" 2>/dev/null       | head -c 400 | grep -o '"title":"[^"]*"' | head -1 | cut -d'"' -f4)
    # Suggest a port that is actually free, rather than naming the taken one.
    alternate=$((ALFRED_PORT + 100))
    echo >&2
    if [ "$occupant" = "Alfred API" ]; then
      echo "  Alfred is already running on port $ALFRED_PORT." >&2
      echo >&2
      echo "  Stop it first:                  ./al stop" >&2
      echo "  or start a second stack:        ALFRED_PORT=$alternate ./al dev" >&2
    else
      echo "  Port $ALFRED_PORT is already answering, and not as Alfred." >&2
      echo "  Starting here would look fine and be wrong: the container would" >&2
      echo "  serve correctly on its own network while every request from your" >&2
      echo "  machine reached whatever holds the port." >&2
      echo >&2
      echo "  It identifies itself as:  ${occupant:-(no OpenAPI document)}" >&2
      echo >&2
      echo "  Start elsewhere instead:  ALFRED_PORT=$alternate ./al dev" >&2
    fi
    echo >&2
    exit 1
  fi

  warnIfExposed
  echo "Alfred! running dev $1  (http://localhost:$ALFRED_PORT)"
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
  docker compose down && \
  docker run --rm -it -v ${PWD}:/docs -v ${PWD}/alfred/site/:/site/ --user $(id -u):$(id -g) squidfunk/mkdocs-material build -d /site/ && \
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
  # Record the @recipe walkthroughs as video and put them where the cookbook
  # links them. Needs a running dev stack; the recordings are what the docs
  # show, and a recipe that fails leaves no video rather than a stale one.
  cd website &&     npx playwright test --project=docs --reporter=json > recipe-report.json &&     node e2e/collect-recipe-videos.js &&     node e2e/cookbook.js
  cd ..

elif [ $1 = "cookbook" ]; then
  shift
  # Regenerate docs/cookbook.md from the end-to-end specs. The tests are the
  # source; the prose is a build artefact. tests/unit/test_cookbook.py fails if
  # the committed file drifts from them.
  node website/e2e/cookbook.js "$@"

elif [ $1 = "flower" ]; then
  shift
  # Celery monitoring on http://localhost:5555. Needs the dev stack up for the
  # broker; flower.yml only brings up flower itself.
  docker compose -f flower.yml up "$@"

elif [ $1 = "demo" -o $1 = "download" -o $1 = "samples" ]; then
  shift
  downloadMedia

# Starts development without the renderer
elif [ $1 = "thin" ]; then
  shift
  ensureDevKey
  ALFRED_PORT="${ALFRED_PORT:-8000}"
  warnIfExposed
  echo "Alfred! thin dev stack, no renderer  (http://localhost:$ALFRED_PORT)"
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
  # build documentation and serve locally, with hot reloader
  shift
  mkdocs serve -a 0.0.0.0:4000

elif [ $1 = "docker" -o $1 = "dock" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml "$@"

elif [ $1 = "t" -o $1 = "test" -o $1 = "e2e" ]; then
  shift
  # --build, as CI runs it, so a local run tests this checkout's images rather
  # than whichever ones an earlier run left behind. --renew-anon-volumes for
  # the same reason: the site's node_modules and the database are anonymous
  # volumes, and compose hands a recreated container its old ones -- so after
  # a dependency change the bundle was built against the previous install.
  docker compose -f test_e2e.yml up --build --renew-anon-volumes --exit-code-from e2e "$@"

elif [ $1 = "pt" -o $1 = "pytest" -o $1 = "py" ]; then
  shift
  docker compose -f pytest.yml up --exit-code-from pytest "$@"

elif [ $1 = "n" -o $1 = "nox" ]; then
  shift
  # In the container, like every other command here. This ran `nox` on the
  # host, which is not a documented prerequisite and is not installed by
  # `./al init` -- so `./al nox -s lint`, which AGENTS.md and CONTRIBUTING.md
  # both name as the pre-pull-request gate, failed with `nox: command not
  # found` for anyone who followed the instructions.
  docker compose -f pytest.yml run --rm pytest -f tests/noxfile.py "$@"

else
  echo "Unknown command: $1"
  echo "Error when running $@"
  echo "$HELP"

fi
