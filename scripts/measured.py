"""Print what the recipes' runs left and what became of it, from a database.

    python scripts/measured.py [--db mongodb://...] [--name db] [--json]

`--db` is the database as ALFRED_HOST_DB names it, mongodb://127.0.0.1:27018
unless set, and `--name` the database's name, DB_NAME or the host run's, `alfred`. Reads every
project and every render, and prints `alfred.core.utils.measured.lines`, or
the report as JSON with `--json`. Changes nothing. `./al measured` runs it
with the virtualenv's Python.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alfred.core.utils import measured  # noqa: E402

DEFAULT_DB = 'mongodb://127.0.0.1:27018'
# The host run's database name (scripts/host.py).
HOST_DB_NAME = 'alfred'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--db', default=os.environ.get('ALFRED_HOST_DB') or DEFAULT_DB)
    parser.add_argument('--name', default=os.environ.get('DB_NAME') or HOST_DB_NAME)
    parser.add_argument('--json', action='store_true', help='the report as JSON')
    args = parser.parse_args(argv)
    from pymongo import MongoClient

    client = MongoClient(args.db, serverSelectionTimeoutMS=5000)
    database = client[args.name]
    projects = list(
        database['Project'].find(
            {}, {'name': 1, 'source': 1, 'edl.duration': 1, 'drafts_dropped': 1}
        )
    )
    renders = list(database['Render'].find({}, {'project_id': 1, 'duration': 1}))
    found = measured.report(projects, renders)
    if args.json:
        print(json.dumps(found, indent=1, default=str))
    else:
        for line in measured.lines(found):
            print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
