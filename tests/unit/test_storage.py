"""What the server keeps on disk, and when it lets go of it.

Files were written and never removed. These pin the lifecycle: what is swept
when it ages, what goes when its render is deleted, how render outputs left
in the media library are moved out of it, and that nothing else is touched on
the way. The database is a small fake here, answering the queries storage.py
asks; `integration/test_storage_commands.py` asks a real one.
"""

import os
from pathlib import Path

import pytest
from bson import ObjectId

from alfred.core.utils import storage

NOW = 1_800_000_000

RENDER_ID = '6a0000000000000000000001'
OTHER_ID = '6a0000000000000000000002'


def aged(path, age, content=b'x'):
    path.write_bytes(content)
    os.utime(path, (NOW - age, NOW - age))
    return path


class TestSweep:
    def test_removes_what_is_older_than_the_limit(self, tmp_path):
        old = aged(tmp_path / 'old', 120)
        fresh = aged(tmp_path / 'fresh', 30)
        assert storage.sweep(tmp_path, 60, now=NOW) == 1
        assert not old.exists() and fresh.exists()

    def test_exactly_the_limit_is_kept(self, tmp_path):
        edge = aged(tmp_path / 'edge', 60)
        assert storage.sweep(tmp_path, 60, now=NOW) == 0
        assert edge.exists()

    def test_only_names_it_is_told_to(self, tmp_path):
        mine = aged(tmp_path / 'frame.jpg', 120)
        other = aged(tmp_path / 'notes.txt', 120)
        jpegs = lambda name: name.endswith('.jpg')  # noqa: E731
        assert storage.sweep(tmp_path, 60, now=NOW, matches=jpegs) == 1
        assert not mine.exists() and other.exists()

    def test_never_a_directory_or_what_is_in_it(self, tmp_path):
        inner = tmp_path / 'inner'
        inner.mkdir()
        nested = aged(inner / 'old', 120)
        os.utime(inner, (NOW - 120, NOW - 120))
        assert storage.sweep(tmp_path, 60, now=NOW) == 0
        assert nested.exists()

    def test_never_through_a_symlink(self, tmp_path):
        outside = tmp_path / 'outside'
        outside.mkdir()
        target = aged(outside / 'keep', 120)
        swept = tmp_path / 'swept'
        swept.mkdir()
        try:
            (swept / 'link').symlink_to(target)
        except OSError:
            pytest.skip('cannot create symlinks here')
        assert storage.sweep(swept, 60, now=NOW) == 0
        assert target.exists()

    def test_a_missing_directory_is_nothing_to_do(self, tmp_path):
        assert storage.sweep(tmp_path / 'absent', 60, now=NOW) == 0


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """A library, its render directory, and a delivery directory."""
    from alfred import config

    library = tmp_path / 'videos'
    renders = library / 'renders'
    deliveries = tmp_path / 'deliveries'
    for path in (renders, deliveries):
        path.mkdir(parents=True)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(library))
    monkeypatch.setattr(config, 'RENDER_DIR', str(renders))
    monkeypatch.setattr(config, 'DELIVERY_DIR', str(deliveries))
    return library, renders, deliveries


def names(paths):
    return sorted(Path(path).name for path in paths)


class TestARendersOwnFiles:
    def test_are_its_output_and_its_delivery_copy(self, dirs):
        _, renders, deliveries = dirs
        name = f'{RENDER_ID}.mp4'
        (renders / name).write_bytes(b'out')
        (deliveries / name).write_bytes(b'copy')
        assert names(storage.remove_render_files(RENDER_ID, name)) == [name, name]
        assert not (renders / name).exists() and not (deliveries / name).exists()

    def test_and_no_other_render_s(self, dirs):
        _, renders, _ = dirs
        (renders / f'{OTHER_ID}.mp4').write_bytes(b'theirs')
        storage.remove_render_files(RENDER_ID, f'{RENDER_ID}.mp4')
        assert (renders / f'{OTHER_ID}.mp4').exists()

    def test_a_name_not_built_from_its_id_is_left_alone(self, dirs):
        """A render stored before outputs were named by id: its file may be in
        the library, where people use it as media."""
        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'legacy')
        (renders / 'old_render.mp4').write_bytes(b'legacy')
        assert storage.remove_render_files(RENDER_ID, 'old_render.mp4') == []
        assert (library / 'old_render.mp4').exists()
        assert (renders / 'old_render.mp4').exists()

    def test_a_filename_naming_another_render_is_left_alone(self, dirs):
        _, renders, _ = dirs
        (renders / f'{OTHER_ID}.mp4').write_bytes(b'theirs')
        assert storage.remove_render_files(RENDER_ID, f'{OTHER_ID}.mp4') == []
        assert (renders / f'{OTHER_ID}.mp4').exists()

    def test_nothing_there_is_nothing_to_do(self, dirs):
        assert storage.remove_render_files(RENDER_ID, f'{RENDER_ID}.mp4') == []
        assert storage.remove_render_files(RENDER_ID, None) == []


class FakeCollection:
    """`find` for the query shapes storage.py asks, and nothing else."""

    def __init__(self, *documents):
        self.documents = list(documents)

    def find(self, query, projection=None):
        return [d for d in self.documents if self._matches(d, query)]

    @staticmethod
    def _matches(document, query):
        for key, condition in query.items():
            if key == 'edl.clips.name':
                clips = document.get('edl', {}).get('clips', [])
                if condition not in [c.get('name') for c in clips]:
                    return False
            elif condition == {'$type': 'string'}:
                if not isinstance(document.get(key), str):
                    return False
            elif isinstance(condition, dict) and '$in' in condition:
                if document.get(key) not in condition['$in']:
                    return False
            elif document.get(key) != condition:
                return False
        return True


class FakeDb:
    def __init__(self, renders=(), projects=()):
        self.Render = FakeCollection(*renders)
        self.Project = FakeCollection(*projects)


def render_doc(filename, render_id=None, clips=()):
    return {
        '_id': ObjectId(render_id) if render_id else ObjectId(),
        'filename': filename,
        'edl': {'clips': list(clips)},
    }


def project_doc(name, *clip_names):
    return {
        '_id': f'p-{name}',
        'name': name,
        'edl': {'clips': [{'type': 'video', 'name': n} for n in clip_names]},
    }


class TestPlanningTheMigration:
    def test_finds_render_outputs_in_the_library(self, dirs):
        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'12345')
        (library / 'just-media.mp4').write_bytes(b'not a render')
        (move,) = storage.plan_migration(FakeDb(renders=[render_doc('old_render.mp4')]))
        assert move.filename == 'old_render.mp4'
        assert move.size == 5
        assert Path(move.target) == renders.resolve() / 'old_render.mp4'
        assert move.movable()

    def test_an_output_already_in_place_is_not_listed(self, dirs):
        _, renders, _ = dirs
        (renders / f'{RENDER_ID}.mp4').write_bytes(b'x')
        db = FakeDb(renders=[render_doc(f'{RENDER_ID}.mp4', RENDER_ID)])
        assert storage.plan_migration(db) == []

    def test_a_file_used_as_a_clip_is_held_back(self, dirs):
        """Moving it would leave those projects naming a file that is gone."""
        library, _, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        db = FakeDb(
            renders=[render_doc('old_render.mp4')],
            projects=[project_doc('Uses it', 'videos/old_render.mp4')],
        )
        (move,) = storage.plan_migration(db)
        assert move.used_by == ["project 'Uses it' (p-Uses it)"]
        assert not move.movable()
        assert move.movable(include_used=True)

    def test_a_render_using_it_as_a_clip_holds_it_back_too(self, dirs):
        library, _, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        user = render_doc(
            f'{OTHER_ID}.mp4', OTHER_ID, clips=[{'name': 'videos/old_render.mp4'}]
        )
        db = FakeDb(renders=[render_doc('old_render.mp4'), user])
        (move,) = storage.plan_migration(db)
        assert move.used_by == [f'render {OTHER_ID}']

    def test_a_name_already_taken_in_the_render_directory_is_held_back(self, dirs):
        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'one')
        (renders / 'old_render.mp4').write_bytes(b'another')
        (move,) = storage.plan_migration(FakeDb(renders=[render_doc('old_render.mp4')]))
        assert move.target_taken
        assert not move.movable(include_used=True)

    def test_a_stored_name_that_would_leave_the_library_finds_nothing(
        self, dirs, tmp_path
    ):
        (tmp_path / 'secret.mp4').write_bytes(b'x')
        assert (
            storage.plan_migration(FakeDb(renders=[render_doc('../secret.mp4')])) == []
        )


def migrate(db, *args):
    lines = []
    code = storage.migrate_command(
        db,
        apply='--apply' in args,
        include_used='--include-used' in args,
        out=lines.append,
    )
    return code, lines


class TestTheMigrationCommand:
    def test_is_a_dry_run_unless_told_otherwise(self, dirs):
        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        code, lines = migrate(FakeDb(renders=[render_doc('old_render.mp4')]))
        assert code == 0
        assert (library / 'old_render.mp4').exists()
        assert not (renders / 'old_render.mp4').exists()
        assert lines[0].startswith(
            'would move: videos/old_render.mp4 -> videos/renders/old_render.mp4'
        )
        assert lines[-1].startswith('Dry run: 1 of 1 files')

    def test_apply_moves_the_file(self, dirs):
        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'the render')
        code, lines = migrate(FakeDb(renders=[render_doc('old_render.mp4')]), '--apply')
        assert code == 0
        assert not (library / 'old_render.mp4').exists()
        assert (renders / 'old_render.mp4').read_bytes() == b'the render'
        assert lines[0].startswith('moved: ')
        assert lines[-1].startswith('Moved 1 of 1 files')

    def test_after_which_its_download_still_finds_it(self, dirs):
        """`output_path` looks in RENDER_DIR first, then the library."""
        from alfred.core.utils.media import output_path

        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        migrate(FakeDb(renders=[render_doc('old_render.mp4')]), '--apply')
        assert Path(output_path('old_render.mp4')).parent == renders

    def test_and_the_library_no_longer_lists_it(self, dirs):
        from alfred.core.utils.media import library_files

        library, _, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        (library / 'media.mp4').write_bytes(b'x')
        migrate(FakeDb(renders=[render_doc('old_render.mp4')]), '--apply')
        assert library_files(str(library)) == ['media.mp4']

    def test_a_file_in_use_stays_unless_asked(self, dirs):
        library, renders, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        db = FakeDb(
            renders=[render_doc('old_render.mp4')],
            projects=[project_doc('P', 'videos/old_render.mp4')],
        )
        _, lines = migrate(db, '--apply')
        assert (library / 'old_render.mp4').exists()
        assert lines[0].startswith('skipped: ')
        assert 'used as a clip by' in lines[1]
        migrate(db, '--apply', '--include-used')
        assert (renders / 'old_render.mp4').exists()

    def test_the_dry_run_says_why_a_file_in_use_would_stay(self, dirs):
        library, _, _ = dirs
        (library / 'old_render.mp4').write_bytes(b'x')
        db = FakeDb(
            renders=[render_doc('old_render.mp4')],
            projects=[project_doc('P', 'videos/old_render.mp4')],
        )
        _, lines = migrate(db)
        assert lines[0].startswith('would skip: ')
        assert '--include-used' in lines[-1]

    def test_nothing_to_move_says_so(self, dirs):
        code, lines = migrate(FakeDb())
        assert code == 0
        assert lines == ['No render outputs in the media library: nothing to move.']


class TestOrphans:
    def test_files_whose_render_is_gone_are_found(self, dirs):
        _, renders, deliveries = dirs
        (renders / f'{RENDER_ID}.mp4').write_bytes(b'kept')
        (renders / f'{OTHER_ID}.mp4').write_bytes(b'orphan')
        (deliveries / f'{OTHER_ID}.mp4').write_bytes(b'orphan copy')
        (renders / 'legacy-name.mp4').write_bytes(b'not ours to judge')
        db = FakeDb(renders=[render_doc(f'{RENDER_ID}.mp4', RENDER_ID)])
        found = storage.find_orphans(db)
        assert names(o.path for o in found) == [f'{OTHER_ID}.mp4'] * 2

    def test_are_removed_only_when_asked(self, dirs):
        _, renders, _ = dirs
        orphan = renders / f'{OTHER_ID}.mp4'
        orphan.write_bytes(b'orphan')
        lines = []
        storage.orphans_command(FakeDb(), out=lines.append)
        assert orphan.exists()
        assert lines[-1].startswith('Dry run: 1 files')
        storage.orphans_command(FakeDb(), apply=True, out=lines.append)
        assert not orphan.exists()

    def test_none_says_so(self, dirs):
        lines = []
        assert storage.orphans_command(FakeDb(), out=lines.append) == 0
        assert lines == ['No files left behind by deleted renders.']


class TestTheCommandLine:
    def test_needs_a_command(self):
        with pytest.raises(SystemExit):
            storage.main([], db=FakeDb())

    def test_runs_the_migration(self, dirs):
        assert storage.main(['migrate'], db=FakeDb()) == 0

    def test_runs_the_orphan_report(self, dirs):
        assert storage.main(['orphans'], db=FakeDb()) == 0
