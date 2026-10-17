"""C4 -- what a clip may name as media, and where that resolves.

A media clip's `name` used to be opened exactly as sent: relative to whichever
process opened it, absolute paths anywhere on the machine, and any URL. Found
by rendering a clip dragged from the media bin: the worker, started in
/app/alfred, looked for `videos/demo-bars.mp4` there and failed every render,
while an EDL naming `/etc/hostname` had the worker open that file.

These pin the rule in `alfred.core.utils.media`: a library path exactly as
`GET /videos` lists it, or an http(s) URL on an allowed host; resolved against
VIDEO_DIR and never against a working directory.
"""

import os
from os.path import isabs, join

import pytest
from otto.models import Clip, Edl, TemplateData

from alfred import config
from alfred.core.routes.templates import TEMPLATE_NAMES
from alfred.core.utils.media import (
    LIBRARY_PREFIX,
    MediaNameError,
    RefusedEdl,
    check_edl,
    check_media_name,
    library_file,
    library_files,
    resolve_edl,
)


@pytest.fixture
def library(tmp_path):
    """A media library with one clip in it, and a file just outside it."""
    root = tmp_path / 'videos'
    root.mkdir()
    (root / 'clip.mp4').write_bytes(b'not really a video')
    (tmp_path / 'outside.mp4').write_bytes(b'not in the library')
    return root


def check(name, library, hosts=()):
    return check_media_name(name, video_dir=str(library), remote_hosts=hosts)


class TestLibraryPaths:
    def test_a_listed_name_resolves_into_the_library(self, library):
        path = check('videos/clip.mp4', library)
        assert path == join(str(library), 'clip.mp4')

    def test_the_resolved_path_is_absolute(self, library, tmp_path, monkeypatch):
        """Absolute, so the engine's working directory cannot change it."""
        monkeypatch.chdir(tmp_path)
        assert isabs(check_media_name('videos/clip.mp4', video_dir='videos'))

    def test_resolution_does_not_depend_on_the_working_directory(
        self, library, tmp_path, monkeypatch
    ):
        """The defect itself: the worker ran in a directory with no videos/."""
        elsewhere = tmp_path / 'alfred'
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert os.path.isfile(check('videos/clip.mp4', library))

    def test_the_prefix_is_what_the_media_list_uses(self):
        assert LIBRARY_PREFIX == 'videos/'

    def test_a_missing_file_is_refused(self, library):
        with pytest.raises(MediaNameError, match='no such file'):
            check('videos/nope.mp4', library)

    def test_a_directory_is_refused(self, library):
        (library / 'renders').mkdir()
        with pytest.raises(MediaNameError):
            check('videos/renders', library)


REFUSED = [
    pytest.param('/etc/hostname', id='absolute'),
    pytest.param('/app/videos/clip.mp4', id='absolute-into-the-library'),
    pytest.param('videos/../outside.mp4', id='dotdot-out'),
    pytest.param('videos/../videos/clip.mp4', id='dotdot-back-in'),
    pytest.param('../videos/clip.mp4', id='leading-dotdot'),
    pytest.param('videos/..', id='bare-dotdot'),
    pytest.param('videos\\clip.mp4', id='backslash'),
    pytest.param('videos/..\\outside.mp4', id='backslash-dotdot'),
    pytest.param('videos/clip.mp4\x00.png', id='nul'),
    pytest.param('videos/clip\n.mp4', id='newline'),
    pytest.param('clip.mp4', id='no-prefix'),
    pytest.param('media/clip.mp4', id='other-directory'),
    pytest.param('videos/sub/clip.mp4', id='nested'),
    pytest.param('videos/', id='prefix-only'),
    pytest.param('videos/.hidden', id='hidden'),
    pytest.param('C:/videos/clip.mp4', id='drive-letter'),
    pytest.param('file:///etc/hostname', id='file-url'),
    pytest.param('ftp://example.test/clip.mp4', id='ftp-url'),
    pytest.param('data:video/mp4;base64,AAAA', id='data-url'),
    pytest.param('', id='empty'),
    pytest.param('   ', id='blank'),
    pytest.param(None, id='none'),
]


@pytest.mark.parametrize('name', REFUSED)
def test_names_outside_the_contract_are_refused(name, library):
    with pytest.raises(MediaNameError):
        check(name, library)


class TestSymlinks:
    def test_a_link_out_of_the_library_is_refused(self, library, tmp_path):
        """Contained after symlinks are followed, not just by spelling."""
        try:
            os.symlink(tmp_path / 'outside.mp4', library / 'escape.mp4')
        except (OSError, NotImplementedError):
            pytest.skip('this platform will not create a symlink here')
        with pytest.raises(MediaNameError):
            check('videos/escape.mp4', library)


class TestRemoteMedia:
    def test_urls_are_refused_by_default(self, library):
        """The default host list is empty: nothing remote unless configured."""
        assert config.parse_hosts('') == frozenset()
        with pytest.raises(MediaNameError, match='not allowed'):
            check('https://example.test/clip.mp4', library)

    def test_the_configured_default_is_used_when_none_is_passed(
        self, library, monkeypatch
    ):
        monkeypatch.setattr(config, 'REMOTE_MEDIA_HOSTS', frozenset({'cdn.test'}))
        url = 'https://cdn.test/clip.mp4'
        assert check_media_name(url, video_dir=str(library)) == url

    @pytest.mark.parametrize('scheme', ['http', 'https'])
    def test_an_allowed_host_passes_through_unchanged(self, library, scheme):
        url = f'{scheme}://cdn.test/a/clip.mp4?x=1'
        assert check(url, library, hosts={'cdn.test'}) == url

    def test_the_host_comparison_ignores_case(self, library):
        assert check('https://CDN.Test/clip.mp4', library, hosts={'cdn.test'})

    def test_a_port_does_not_change_the_host(self, library):
        assert check('https://cdn.test:8443/clip.mp4', library, hosts={'cdn.test'})

    def test_userinfo_cannot_disguise_the_host(self, library):
        """`allowed@evil` is a request to evil."""
        with pytest.raises(MediaNameError):
            check('https://cdn.test@evil.test/clip.mp4', library, hosts={'cdn.test'})

    def test_a_subdomain_is_a_different_host(self, library):
        with pytest.raises(MediaNameError):
            check('https://cdn.test.evil.test/clip.mp4', library, hosts={'cdn.test'})

    def test_the_metadata_address_is_refused(self, library):
        """The request a URL allowlist exists to stop."""
        with pytest.raises(MediaNameError):
            check('http://169.254.169.254/latest/meta-data/', library)

    def test_the_host_list_is_parsed_and_normalised(self):
        assert config.parse_hosts(' CDN.test, ,media.test ') == {
            'cdn.test',
            'media.test',
        }


class TestTheLibraryListing:
    def test_only_names_a_clip_can_use_are_listed(self, library):
        (library / 'renders').mkdir()
        (library / '.DS_Store').write_bytes(b'')
        assert library_files(str(library)) == ['clip.mp4']

    def test_everything_listed_is_accepted_back(self, library):
        """What GET /videos offers and what POST /render accepts are one rule."""
        (library / 'second clip.mp4').write_bytes(b'x')
        for name in library_files(str(library)):
            assert check(LIBRARY_PREFIX + name, library)

    def test_library_file_refuses_a_traversing_name(self, library):
        assert library_file('../outside.mp4', str(library)) is None
        assert library_file('..', str(library)) is None


def template(name='makeColor'):
    return Clip(
        type='template', name=name, duration=1, data=TemplateData(color='#000000')
    )


def media(name='videos/clip.mp4', type='video'):
    return Clip(type=type, name=name, duration=1)


def check_timeline(clips, library, hosts=()):
    check_edl(
        Edl(clips=clips),
        TEMPLATE_NAMES,
        video_dir=str(library),
        remote_hosts=hosts,
    )


class TestWholeTimelines:
    def test_a_timeline_of_library_media_and_templates_passes(self, library):
        check_timeline([template(), media(), media(type='image')], library)

    def test_an_empty_timeline_is_refused(self, library):
        """Refused at the request, not after a worker has picked it up."""
        with pytest.raises(RefusedEdl, match='no clips'):
            check_timeline([], library)

    @pytest.mark.parametrize('kind', ['video', 'image', 'audio'])
    def test_every_media_type_is_checked(self, kind, library):
        with pytest.raises(MediaNameError):
            check_timeline([media('/etc/hostname', type=kind)], library)

    @pytest.mark.parametrize(
        'name', ['rgbToDec', 'ColorClip', 'concatenate_videoclips', 'final', 'nope']
    )
    def test_templates_outside_the_allowlist_are_refused(self, name, library):
        with pytest.raises(RefusedEdl, match='not a template'):
            check_timeline([template(name)], library)

    @pytest.mark.parametrize('kind', ['bogus', None])
    def test_an_unknown_clip_type_is_refused(self, kind, library):
        """Before the engine, which duplicates the previous clip for these."""
        with pytest.raises(RefusedEdl, match='unknown clip type'):
            check_timeline([template(), Clip(type=kind, name='x')], library)

    def test_the_refusal_names_the_clip(self, library):
        with pytest.raises(MediaNameError, match='clip 2'):
            check_timeline([template(), media('../outside.mp4')], library)


class TestResolution:
    def test_library_names_become_absolute_paths(self, library):
        resolved = resolve_edl(
            Edl(clips=[media(), template()]), video_dir=str(library), remote_hosts=()
        )
        assert resolved.clips[0].name == join(str(library), 'clip.mp4')
        assert resolved.clips[1].name == 'makeColor'

    def test_the_original_is_left_as_sent(self, library):
        edl = Edl(clips=[media()])
        resolve_edl(edl, video_dir=str(library), remote_hosts=())
        assert edl.clips[0].name == 'videos/clip.mp4'

    def test_an_allowed_url_is_left_for_the_engine(self, library):
        url = 'https://cdn.test/clip.mp4'
        resolved = resolve_edl(
            Edl(clips=[media(url)]), video_dir=str(library), remote_hosts={'cdn.test'}
        )
        assert resolved.clips[0].name == url

    def test_resolution_refuses_what_checking_refuses(self, library):
        with pytest.raises(MediaNameError):
            resolve_edl(
                Edl(clips=[media('/etc/hostname')]),
                video_dir=str(library),
                remote_hosts=(),
            )


class TestOnlyMediaIsLibraryMedia:
    """The library lists what a clip can open, and nothing an encoder is in
    the middle of writing."""

    @pytest.mark.parametrize(
        'name',
        [
            # otto muxes a render's sound from a temporary beside the output
            '6ad3cdc433bc85ee116c7577.mp4.audio.m4a',
            'clip.audio.m4a',
            # moviepy's own temporaries
            'clipTEMP_MPY_wvf_snd.mp4',
            # not media at all
            'notes.txt',
            'README',
            'archive.zip',
        ],
    )
    def test_is_neither_listed_nor_accepted(self, library, name):
        (library / name).write_bytes(b'x')
        assert name not in library_files(str(library))
        with pytest.raises(MediaNameError):
            check(LIBRARY_PREFIX + name, library)

    @pytest.mark.parametrize(
        'name', ['CLIP.MOV', 'still.png', 'music.mp3', 'song.m4a', 'title.webm']
    )
    def test_media_of_every_clip_type_is(self, library, name):
        (library / name).write_bytes(b'x')
        assert name in library_files(str(library))
        assert check(LIBRARY_PREFIX + name, library)
