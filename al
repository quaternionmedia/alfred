#!/bin/sh
VERSION=v0.1.3

HELP="./al

Init script and helper functions for Alfred

USAGE:
./al COMMAND [args]


COMMANDS:
b | build
bats
d | dev
docker | dock
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
t | test
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
  echo "Alfred! running dev $1"
  docker compose -f docker-compose.yml -f dev.yml up "$@"

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
  docker compose run website yarn install

  # Installs the dependencies.
elif [ $1 = "i" -o $1 = "install" ]; then
    shift
    echo "installing dependencies"
    # make install
    docker compose -f docker-compose.yml run website yarn add "$@"

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
  # DB_URL=mongodb://$1:27017 DB_NAME=alfred CELERY_BROKER=$DB_URL/celery CELERY_BACKEND=$CELERY_BROKER celery -A alfred.core.utils:renderer --workdir alfred/ worker --concurrency=4
  docker compose -f docker-compose.yml -f dev.yml run -it --entrypoint "celery -A alfred.core.utils.tasks:renderer --workdir /app/ -b mongodb://$1:27017/celery --result-backend mongodb://$1:27017/celery worker --loglevel=info --concurrency=1" renderer

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

elif [ $1 = "t" -o $1 = "test" -o $1 = "cy" ]; then
  shift
  docker compose -f test_cy.yml up --exit-code-from cy "$@"

elif [ $1 = "pt" -o $1 = "pytest" -o $1 = "py" ]; then
  shift
  docker compose -f pytest.yml up --exit-code-from pytest "$@"

elif [ $1 = "n" -o $1 = "nox" ]; then
  shift
  nox -f tests/noxfile.py "$@"

elif [ $1 = "bats" -o $1 = "bat" ]; then
  shift
  docker compose -f test_bats.yml up --build --exit-code-from bats "$@"

else
  echo "Unknown command: $1"
  echo "Error when running $@"
  echo "$HELP"

fi
