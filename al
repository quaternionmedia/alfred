#!/bin/sh
VERSION=v0.1.3

HELP="./al
init script for Alfred

USAGE
./al COMMAND [ARGS]

COMMANDS

v | version     Show the version number
d | dev         Start the devlopment server
p | prod        Start the production server
b | build       Build the docker images
init            Initialize repository
i | install     Install a new node dependency
demo            Download sample media
restart         Restart the production image
seed            Seed the database
reseed          Reseed (drop) the database
sh              Start an sh shell to the API
l | log         Show the docker logs
w | worker      Run a rendering worker

dump            Dump the database to a file
restore         Restore the database from a file

reload          Reload the development server
g | git         Restore the git submodules
d | docs        Build the documentation site
docker          Execute a docker compose command

t | test        Run the pytest suite
cy | cypress    Run the Cypress integration tests
bats            Run the bats test suite
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

if [ $1 = "version" -o $1 = "v" -o $1 = "-v" ]; then
  echo $VERSION

# Starts in development (optional "--build")
elif [ $1 = "dev" ] || [ -z $1 ]; then
  if [ !-z ]; then shift; fi
  echo "Alfred! running dev $1"
  docker compose -f docker-compose.yml -f dev.yml up "$@"

# Starts in production.
elif [ $1 = "prod" -o $1 = "production" -o $1 = "p" ]; then
  shift
  echo "Alfred! running production $1"
  docker compose down && \
  docker run --rm -it -v ${PWD}:/docs -v ${PWD}/alfred/site/:/site/ --user $(id -u):$(id -g) squidfunk/mkdocs-material build -d /site/ && \
  docker compose -f docker-compose.yml -f production.yml up --build -d $1

  # Build docker images
elif [ $1 = "build" -o $1 = "b" ]; then
    shift
    echo "Alfred! building docker images"
    docker compose -f docker-compose.yml -f dev.yml build "$@"

# Installs website dependencies.
elif [ $1 = "init" ]; then
  shift
  mkdir -p $(dirname $0)/website/dist
  mkdir -p $(dirname $0)/alfred/videos
  mkdir -p $(dirname $0)/alfred/data
  mkdir -p $(dirname $0)/alfred/site
  echo "installing dependencies"
  # make install
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
  docker compose exec api python3 -c """
from seed import seed
from db import db

if db.projects.count_documents({}) == 0:
  db.projects.insert_many(seed)
"""

elif [ $1 = "reinit" -o $1 = "reseed" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml exec api python3 -c """
from seed import seed
from alfred.core.utils import get_sync_db
db = get_sync_db()
db.Project.drop()
db.Project.insert_many(seed)
"""

elif [ $1 = "sh" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml exec api sh

elif [ $1 = "log" -o $1 = "logs" -o $1 = "l" ]; then
  shift
  docker compose logs -f "$@"

elif [ $1 = "worker" -o $1 = "w" ]; then
  shift
  # . operator used in place of source
  . ./.cred
  # DB_URL=mongodb://$1:27017 CELERY_BROKER=$DB_URL/celery CELERY_BACKEND=$CELERY_BROKER celery -A tasks:renderer --workdir alfred/ -b $CELERY_BROKER --result-backend $CELERY_BACKEND worker --concurrency=4
  DB_URL=mongodb://$1:27017 DB_NAME=alfred CELERY_BROKER=$DB_URL/celery CELERY_BACKEND=$CELERY_BROKER celery -A alfred.core.utils:renderer --workdir alfred/ worker --concurrency=4
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

elif [ $1 = "git" -o $1 = "g" ]; then
  shift
  git pull && git submodule update

elif [ $1 = "docs" -o $1 = "d" ]; then
  # build documentation and serve locally, with hot reloader
  shift
  mkdocs serve -a 0.0.0.0:4000

elif [ $1 = "docker" -o $1 = "dock" ]; then
  shift
  docker compose -f docker-compose.yml -f dev.yml "$@"

elif [ $1 = "test" -o $1 = "t" -o $1 = "cy" ]; then
  shift
  docker compose -f docker-compose.yml -f test_cy.yml up --build --exit-code-from cy

elif [ $1 = "bats" -o $1 = "bat" ]; then
  shift
  docker compose -f test_bats.yml up --build --exit-code-from bats

else
  echo "$HELP"
fi
