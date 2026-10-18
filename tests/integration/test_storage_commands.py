"""`./al storage` against a real MongoDB.

The unit tier answers storage.py's queries with a fake; these ask MongoDB the
same questions -- a render's `filename`, which clips name a file, which ids
are still stored -- so the queries themselves are what is tested.
"""

import uuid

import pytest
from bson import ObjectId

from alfred import config
from alfred.core.utils import storage

pytestmark = pytest.mark.needs_db


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    library = tmp_path / 'videos'
    renders = library / 'renders'
    deliveries = tmp_path / 'deliveries'
    for path in (renders, deliveries):
        path.mkdir(parents=True)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(library))
    monkeypatch.setattr(config, 'RENDER_DIR', str(renders))
    monkeypatch.setattr(config, 'DELIVERY_DIR', str(deliveries))
    return library, renders, deliveries


def unique(prefix):
    return f'{prefix}_{uuid.uuid4().hex[:10]}.mp4'


def test_migrate_moves_an_unused_legacy_output(db, dirs):
    library, renders, _ = dirs
    name = unique('legacy')
    (library / name).write_bytes(b'an old render')
    db.Render.insert_one({'filename': name, 'status': 'RENDERED'})

    assert storage.main(['migrate'], db=db) == 0
    assert (library / name).exists(), 'a dry run moved something'

    assert storage.main(['migrate', '--apply'], db=db) == 0
    assert not (library / name).exists()
    assert (renders / name).read_bytes() == b'an old render'


def test_migrate_holds_back_a_file_a_project_uses(db, dirs):
    library, _, _ = dirs
    name = unique('in_use')
    (library / name).write_bytes(b'x')
    db.Render.insert_one({'filename': name})
    db.Project.insert_one(
        {
            'name': 'uses a legacy render',
            'edl': {'clips': [{'type': 'video', 'name': f'videos/{name}'}]},
        }
    )
    (move,) = [m for m in storage.plan_migration(db) if m.filename == name]
    assert move.used_by and 'uses a legacy render' in move.used_by[0]
    storage.main(['migrate', '--apply'], db=db)
    assert (library / name).exists()


def test_orphans_are_the_files_of_renders_that_are_gone(db, dirs):
    _, renders, deliveries = dirs
    kept, gone = ObjectId(), ObjectId()
    db.Render.insert_one({'_id': kept, 'filename': f'{kept}.mp4'})
    (renders / f'{kept}.mp4').write_bytes(b'kept')
    (renders / f'{gone}.mp4').write_bytes(b'orphan')
    (deliveries / f'{gone}.mp4').write_bytes(b'orphan copy')

    found = sorted(o.path for o in storage.find_orphans(db))
    assert [p.split('/')[-1].split('\\')[-1] for p in found] == [f'{gone}.mp4'] * 2

    assert storage.main(['orphans', '--apply'], db=db) == 0
    assert (renders / f'{kept}.mp4').exists()
    assert not (renders / f'{gone}.mp4').exists()
    assert not (deliveries / f'{gone}.mp4').exists()
