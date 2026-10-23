"""The media, storage and signing settings, read from the environment.

Each takes the environment as an argument, as the other settings in config.py
do, so it can be tested without reimporting the module.
"""

import os

import pytest

from alfred import config
from alfred.config import resolve_remote_cache_dir, resolve_seconds


class TestSeconds:
    def test_unset_or_empty_is_the_default(self):
        assert resolve_seconds({}, 'X', 900) == 900
        assert resolve_seconds({'X': ''}, 'X', 900) == 900
        assert resolve_seconds({'X': '  '}, 'X', 900) == 900

    def test_a_whole_number_is_taken(self):
        assert resolve_seconds({'X': '60'}, 'X', 900) == 60
        assert resolve_seconds({'X': ' 3600 '}, 'X', 900) == 3600

    @pytest.mark.parametrize('value', ['15m', '1.5', '0', '-60', 'soon'])
    def test_anything_else_is_the_default_and_says_so(self, value, capsys):
        """A typo must neither stop the server nor become something nobody
        asked for."""
        assert resolve_seconds({'X': value}, 'X', 900) == 900
        assert 'X=' in capsys.readouterr().err


class TestTheRemoteCache:
    def test_by_default_it_is_hidden_in_the_library(self):
        """Shared by the api and the worker through the library mount, and a
        dotted subdirectory, which the library never lists or serves."""
        path = resolve_remote_cache_dir({}, '/app/videos')
        assert path == os.path.join('/app/videos', '.remote-cache')

    def test_the_engine_s_own_setting_is_honoured(self):
        env = {'OTTO_DOWNLOAD_DIR': '/cache'}
        assert resolve_remote_cache_dir(env, '/app/videos') == '/cache'

    def test_alfred_s_setting_wins(self):
        env = {'ALFRED_REMOTE_CACHE_DIR': '/mine', 'OTTO_DOWNLOAD_DIR': '/theirs'}
        assert resolve_remote_cache_dir(env, '/app/videos') == '/mine'

    def test_empty_counts_as_unset(self):
        """What compose passes for a variable nobody set."""
        env = {'ALFRED_REMOTE_CACHE_DIR': '', 'OTTO_DOWNLOAD_DIR': ''}
        assert resolve_remote_cache_dir(env, 'v') == os.path.join('v', '.remote-cache')

    def test_the_engine_is_told_the_same_directory(self):
        assert os.environ['OTTO_DOWNLOAD_DIR'] == config.REMOTE_CACHE_DIR


class TestDefaults:
    @pytest.mark.parametrize(
        'name,setting,default',
        [
            ('ALFRED_MEDIA_URL_TTL', 'MEDIA_URL_TTL', 15 * 60),
            ('ALFRED_FRAME_TTL', 'FRAME_TTL', 60 * 60),
            ('ALFRED_REMOTE_CACHE_TTL', 'REMOTE_CACHE_TTL', 7 * 24 * 3600),
        ],
    )
    def test_each_lifetime(self, name, setting, default):
        if os.environ.get(name):
            pytest.skip(f'{name} is set for this run')
        assert getattr(config, setting) == default

    def test_preview_frames_are_not_where_anything_is_served(self):
        public = os.path.realpath(config.STATIC_DIR)
        frames = os.path.realpath(config.PREVIEW_DIR)
        assert os.path.commonpath([public, frames]) != public
