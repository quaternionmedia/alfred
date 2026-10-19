"""The media, storage and signing settings, read from the environment.

Each takes the environment as an argument, as the other settings in config.py
do, so it can be tested without reimporting the module.
"""

import os
import subprocess
import sys

import pytest

from alfred import config
from alfred.config import resolve_remote_cache_dir, resolve_seconds, resolve_text


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


class TestText:
    def test_unset_or_empty_is_the_default(self):
        assert resolve_text({}, 'X', 'deliveries') == 'deliveries'
        assert resolve_text({'X': ''}, 'X', 'deliveries') == 'deliveries'
        assert resolve_text({'X': '   '}, 'X', 'deliveries') == 'deliveries'

    def test_a_value_is_taken_without_its_surrounding_space(self):
        assert resolve_text({'X': ' /srv/out '}, 'X', 'deliveries') == '/srv/out'

    def test_the_settings_an_empty_value_used_to_mean_literally(self):
        """An empty ALFRED_RENDER_DIR or ALFRED_DELIVERY_DIR was the working
        directory, an empty ALFRED_DEV_USER_EMAIL nobody and an empty
        ALFRED_BUCKET_NAME no bucket. Read as config.py reads them at import,
        in a process of their own so this one's settings stay as they are."""
        names = {
            'ALFRED_RENDER_DIR': 'RENDER_DIR',
            'ALFRED_DELIVERY_DIR': 'DELIVERY_DIR',
            'ALFRED_DEV_USER_EMAIL': 'DEV_USER_EMAIL',
            'ALFRED_BUCKET_NAME': 'BUCKET_NAME',
        }
        env = {key: value for key, value in os.environ.items() if key not in names}
        env.update({name: '' for name in names})
        env.pop('ALFRED_PRODUCTION', None)
        script = (
            'from alfred import config; '
            f"print('|'.join(str(getattr(config, n)) for n in {list(names.values())!r}))"
        )
        run = subprocess.run(
            [sys.executable, '-c', script],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        last_line = run.stdout.strip().splitlines()[-1]
        render_dir, delivery_dir, dev_email, bucket = last_line.split('|')
        assert render_dir == os.path.join(config.VIDEO_DIR, 'renders')
        assert delivery_dir == 'deliveries'
        assert dev_email == config.DEFAULT_DEV_USER_EMAIL
        assert bucket == 'tower-renders'


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
