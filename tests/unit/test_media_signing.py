"""M1 -- signed media URLs, the signing itself.

A signed URL lets a browser fetch one file by itself, with no session: what a
`<video src>` or `<img src>` needs. Holding one is permission to GET exactly
that path until `exp`. These pin the construction (so another client can rely
on the contract), and every way a URL must stop working: expired, tampered
with, used for another path, or signed with another key.
"""

import base64
import hashlib
import hmac
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from alfred import config
from alfred.core.utils import signing

NOW = 1_800_000_000  # a fixed clock, so expiries are exact


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(config, 'SECRET_KEY', 'test-signing-secret-of-some-length')
    monkeypatch.setattr(config, 'MEDIA_URL_TTL', 900)


def parts(url):
    split = urlsplit(url)
    query = {name: values[0] for name, values in parse_qs(split.query).items()}
    return split.path, query['exp'], query['sig']


class TestTheShape:
    def test_path_then_exp_then_sig(self):
        url = signing.media_url('/render/abc/download', now=NOW)
        assert re.fullmatch(
            r'/render/abc/download\?exp=\d+&sig=[A-Za-z0-9_-]{43}', url
        ), url

    def test_the_signature_is_the_contract_s_hmac(self):
        """HMAC-SHA256 over "GET\\n<path>\\n<exp>", keyed by
        HMAC-SHA256(secret, b"alfred-media-v1"), urlsafe base64, unpadded."""
        path, exp, sig = parts(signing.media_url('/videos/clip.mp4', now=NOW))
        key = hmac.new(
            b'test-signing-secret-of-some-length', b'alfred-media-v1', hashlib.sha256
        ).digest()
        mac = hmac.new(key, f'GET\n{path}\n{exp}'.encode(), hashlib.sha256).digest()
        assert sig == base64.urlsafe_b64encode(mac).rstrip(b'=').decode()

    def test_it_lasts_at_least_the_ttl_and_at_most_a_minute_more(self):
        _, exp, _ = parts(signing.media_url('/x', now=NOW))
        assert NOW + 900 <= int(exp) < NOW + 900 + signing.EXPIRY_STEP

    def test_a_ttl_can_be_asked_for(self):
        _, exp, _ = parts(signing.media_url('/x', ttl=60, now=NOW))
        assert NOW + 60 <= int(exp) < NOW + 120

    def test_the_default_ttl_is_the_setting(self, monkeypatch):
        monkeypatch.setattr(config, 'MEDIA_URL_TTL', 3600)
        _, exp, _ = parts(signing.media_url('/x', now=NOW))
        assert NOW + 3600 <= int(exp) < NOW + 3660

    def test_urls_issued_in_the_same_minute_are_the_same_url(self):
        """So a browser's cache, keyed by URL, still works across listings."""
        start = NOW - NOW % 60
        assert signing.media_url('/x', now=start + 1) == signing.media_url(
            '/x', now=start + 59
        )

    def test_a_path_is_percent_encoded_and_signed_as_decoded(self):
        url = signing.media_url('/videos/my clip #2.mp4', now=NOW)
        path, exp, sig = parts(url)
        assert path == '/videos/my%20clip%20%232.mp4'
        assert signing.check('/videos/my clip #2.mp4', exp, sig, now=NOW) is None


class TestWhatItAdmits:
    def test_its_own_path_until_it_expires(self):
        path, exp, sig = parts(signing.media_url('/x', now=NOW))
        assert signing.check('/x', exp, sig, now=NOW) is None
        assert signing.check('/x', exp, sig, now=int(exp)) is None

    def test_not_after(self):
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        assert signing.check('/x', exp, sig, now=int(exp) + 1) == signing.EXPIRED

    def test_not_another_path(self):
        _, exp, sig = parts(signing.media_url('/render/a/download', now=NOW))
        assert signing.check('/render/b/download', exp, sig, now=NOW) == signing.INVALID

    def test_not_a_later_expiry(self):
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        later = str(int(exp) + 3600)
        assert signing.check('/x', later, sig, now=NOW) == signing.INVALID

    def test_not_a_changed_signature(self):
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        changed = ('A' if sig[0] != 'A' else 'B') + sig[1:]
        assert signing.check('/x', exp, changed, now=NOW) == signing.INVALID

    def test_not_one_signed_with_another_key(self, monkeypatch):
        """Changing ALFRED_SECRET_KEY revokes every URL issued with the old one."""
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        monkeypatch.setattr(config, 'SECRET_KEY', 'a-different-secret-entirely-000')
        assert signing.check('/x', exp, sig, now=NOW) == signing.INVALID

    def test_not_one_with_padding_added(self):
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        assert signing.check('/x', exp, sig + '=', now=NOW) == signing.INVALID

    @pytest.mark.parametrize(
        'exp', [None, '', 'soon', '-1', '1e9', ' 123', '0123', '١٢٣', '9' * 5000]
    )
    def test_not_a_malformed_expiry(self, exp):
        assert signing.check('/x', exp, 'sig', now=NOW) == signing.INVALID

    def test_not_a_missing_signature(self):
        _, exp, _ = parts(signing.media_url('/x', now=NOW))
        assert signing.check('/x', exp, None, now=NOW) == signing.INVALID
        assert signing.check('/x', exp, '', now=NOW) == signing.INVALID


class TestWithoutAKey:
    """The development stub leaves ALFRED_SECRET_KEY empty."""

    @pytest.mark.parametrize('empty', [None, ''])
    def test_urls_still_work_in_this_process(self, monkeypatch, empty):
        monkeypatch.setattr(config, 'SECRET_KEY', empty)
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        assert signing.check('/x', exp, sig, now=NOW) is None

    def test_but_are_not_signed_with_the_empty_secret(self, monkeypatch):
        """Which anyone could reproduce, and so forge."""
        monkeypatch.setattr(config, 'SECRET_KEY', '')
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        key = hmac.new(b'', b'alfred-media-v1', hashlib.sha256).digest()
        forged = base64.urlsafe_b64encode(
            hmac.new(key, f'GET\n/x\n{exp}'.encode(), hashlib.sha256).digest()
        )
        assert sig != forged.rstrip(b'=').decode()

    def test_and_a_configured_key_s_urls_are_not_its(self, monkeypatch):
        _, exp, sig = parts(signing.media_url('/x', now=NOW))
        monkeypatch.setattr(config, 'SECRET_KEY', '')
        assert signing.check('/x', exp, sig, now=NOW) == signing.INVALID


class TestTheKeyIsItsOwn:
    def test_a_session_token_signature_is_not_a_media_signature(self):
        """The media key is derived from the secret, never the secret itself,
        so nothing else the secret signs can pass for a media URL."""
        _, exp, _ = parts(signing.media_url('/x', now=NOW))
        raw = hmac.new(
            b'test-signing-secret-of-some-length',
            f'GET\n/x\n{exp}'.encode(),
            hashlib.sha256,
        ).digest()
        forged = base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
        assert signing.check('/x', exp, forged, now=NOW) == signing.INVALID


class TestTheRoutePath:
    def test_is_the_path(self):
        assert signing.route_path({'path': '/videos/x.mp4'}) == '/videos/x.mp4'

    def test_without_a_proxy_s_root_path(self):
        scope = {'path': '/alfred/videos/x.mp4', 'root_path': '/alfred'}
        assert signing.route_path(scope) == '/videos/x.mp4'

    def test_a_root_path_that_is_only_a_prefix_of_a_segment_stays(self):
        scope = {'path': '/alfredo/videos/x.mp4', 'root_path': '/alfred'}
        assert signing.route_path(scope) == '/alfredo/videos/x.mp4'
