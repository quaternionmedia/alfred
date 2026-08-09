#!/bin/sh
VERSION=v0.1.3

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
    echo
    echo "  Port $ALFRED_PORT is already answering." >&2
    echo "  Something else is bound there; this stack would look up while every" >&2
    echo "  request from your machine reached that instead." >&2
    echo >&2
    echo "  It identifies itself as:" >&2
    curl -s --max-time 3 "http://localhost:$ALFRED_PORT/openapi.json" 2>/dev/null       | head -c 300 | grep -o '"title":"[^"]*"' | head -1 | sed 's/^/    /' >&2       || echo "    (no OpenAPI document; not a FastAPI app, or not sharing one)" >&2
    echo >&2
    echo "  Start on another port instead:  ALFRED_PORT=8100 ./al dev" >&2
    echo >&2
    exit 1
  fi

  echo "Alfred! running dev $1  (http://localhost:$ALFRED_PORT)"
  ALFRED_PORT="$ALFRED_PORT" docker compose -f docker-compose.yml -f dev.yml up "$@"

# Starts in production.
elif [ $1 = "p" -o $1 = "production" -o $1 = "prod" ]; then
  shift
  echo "Alfred! running production $1"
  docker compose down && \
  docker run --rm -it -v ${PWD}:/docs -v ${PWD}/alfred/site/:/site/ --user $(id -u):$(id -g) squidfunk/mkdocs-material build -d /site/ && \
  docker compose -f docker-compose.yml -f production.yml up --build -d $1

# Installs website dependencies.
elif [ $1 = "init" ]; then
  shift
  mkdir -p $(dirname $0)/website/dist
  mkdir -p $(dirname $0)/alfred/videos
  mkdir -p $(dirname $0)/alfred/data
  mkdir -p $(dirname $0)/alfred/site
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

elif [ $1 = "restart" -o $1 = "r" ]; then
  shift
  docker compose -f docker-compose.yml -f production.yml restart

elif [ $1 = "seed" -o $1 = "db" ]; then
  shift
  docker compose exec api python3.10 -c """
from seed import seed
from db import db

if db.projects.count_documents({}) == 0:
  db.projects.insert_many(seed)
"""

elif [ $1 = "reinit" -o $1 = "reseed" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml exec api python3.10 -c """
from seed import seed
from alfred.core.utils import get_sync_db
db = get_sync_db()
db.Project.drop()
db.Project.insert_many(seed)
"""

elif [ $1 = "sh" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml exec api sh "$@"

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
  docker compose exec db sh -c "mongodump --db alfred --gzip --archive=$FILENAME"
  docker container cp alfred_db_1:$FILENAME $FILENAME

elif [ $1 = "restore" ]; then
  shift
  docker container cp $1 alfred_db_1:/$1
  docker compose exec db sh -c "mongorestore --gzip --db alfred --archive=/$1 --drop"

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
  docker compose -f test_e2e.yml up --exit-code-from e2e "$@"

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
