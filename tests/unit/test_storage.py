"""What the server keeps on disk, and when it lets go of it.

Files were written and never removed. These pin the lifecycle: what is swept
when it ages, and that nothing else is touched on the way.
"""

import os

import pytest

from alfred.core.utils import storage

NOW = 1_800_000_000


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
