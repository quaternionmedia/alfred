"""`./al share`: alfred's family, shared from one host to invited devices.

scripts/share.py keeps one standing share apart from every development stack.
What is tested here is what decides whether a share is safe to reach and
says what it serves: the compose file it writes (the commit's own image,
production settings, no login bypass, the api alone published and only on
the manifest's addresses), the addresses and ports it refuses or keeps clear
of, that a commit nobody else can fetch is refused, that a snapshot holds the
database and the media and a restore replaces them whole, and that a
password reaches the container on standard input and never on a command
line.

The share itself, built and started against Docker, is run by hand
(docs/share.md), as `./al family loop` is.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
COMMIT = 'a' * 40


def load():
    sys.path.insert(0, str(REPO / 'scripts'))
    spec = importlib.util.spec_from_file_location('share', REPO / 'scripts' / 'share.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


share = load()


def manifest(*addresses, members=('alfred', 'joe')):
    made = share.new_manifest(addresses or ('10.9.8.7',))
    for name in members:
        made['members'][name] = {'ref': 'main', 'commit': COMMIT}
    return made


def document(made, tmp_path, env=None):
    return share.compose_document(made, tmp_path, env=env or {})


# --- the compose file ---------------------------------------------------------


def test_the_api_is_published_on_the_manifests_addresses_and_nowhere_else(tmp_path):
    services = document(manifest('10.9.8.7'), tmp_path)['services']
    assert services['api']['ports'] == ['127.0.0.1:17320:80', '10.9.8.7:17320:80']
    for name in ('db', 'renderer', 'site'):
        assert 'ports' not in services[name], f'{name} is published'


def test_alfred_runs_in_production_with_registration_closed(tmp_path):
    settings = document(manifest(), tmp_path)['services']['api']['environment']
    assert settings['ALFRED_PRODUCTION'] == 'true'
    assert settings['ALFRED_ALLOW_REGISTRATION'] == 'false'


def test_the_login_bypass_never_reaches_a_share(tmp_path, monkeypatch):
    made = manifest()
    made['members']['alfred']['env'] = {'ALFRED_DEV_SKIP_AUTH': '1'}
    monkeypatch.setenv('ALFRED_DEV_SKIP_AUTH', '1')
    services = share.compose_document(made, tmp_path)['services']
    for name in ('api', 'renderer'):
        assert 'ALFRED_DEV_SKIP_AUTH' not in services[name]['environment']


def test_the_code_is_the_images_and_nothing_is_mounted_over_it(tmp_path):
    services = document(manifest(), tmp_path)['services']
    for name in ('api', 'renderer'):
        targets = [volume.rsplit(':', 1)[-1] for volume in services[name]['volumes']]
        assert '/app' not in targets and '/app/alfred' not in targets, name
    build = services['api']['build']
    assert build['context'] == (tmp_path / 'src' / 'alfred').resolve().as_posix()
    assert build['labels']['org.opencontainers.image.revision'] == COMMIT


def test_the_database_and_media_are_the_shares(tmp_path):
    services = document(manifest(), tmp_path)['services']
    root = tmp_path.resolve().as_posix()
    assert services['db']['volumes'] == [f'{root}/db:/data/db']
    assert f'{root}/videos:/app/videos' in services['api']['volumes']
    assert f'{root}/videos:/app/videos' in services['renderer']['volumes']


def test_what_serves_comes_back_with_its_host(tmp_path):
    services = document(manifest(), tmp_path)['services']
    for name in share.LONG_RUNNING:
        assert services[name]['restart'] == 'unless-stopped', name
    assert services['site']['restart'] == 'no'


def test_each_container_says_which_commit_it_runs(tmp_path):
    services = document(manifest(), tmp_path)['services']
    for name in ('api', 'renderer', 'site'):
        assert services[name]['labels']['qm.share.commit'] == COMMIT, name


def test_alfred_reaches_the_members_it_drives_on_their_share_ports(tmp_path):
    settings = document(
        manifest(members=('alfred', 'joe', 'looksatwords')), tmp_path
    )['services']['api']['environment']
    assert settings['ALFRED_AUDIO_ENGINE_URL'] == 'http://host.docker.internal:10594'
    assert settings['ALFRED_LANGUAGE_ENGINE_URL'] == 'http://host.docker.internal:14142'


def test_a_member_left_out_of_the_manifest_is_not_wired(tmp_path):
    settings = document(manifest(members=('alfred',)), tmp_path)['services']['api'][
        'environment'
    ]
    assert 'ALFRED_AUDIO_ENGINE_URL' not in settings
    assert 'ALFRED_LANGUAGE_ENGINE_URL' not in settings


def test_the_database_has_no_way_out(tmp_path):
    made = document(manifest(), tmp_path)
    assert made['services']['db']['networks'] == ['isolated']
    assert made['networks']['isolated'] == {'internal': True}


# --- addresses and ports ------------------------------------------------------


@pytest.mark.parametrize('address', ['0.0.0.0', '::'])
def test_every_interface_is_refused(tmp_path, address):
    args = SimpleNamespace(address=[address], members=[])
    with pytest.raises(share.Refused, match='every interface'):
        share.init(args, tmp_path)
    assert not share.manifest_path(tmp_path).exists()


def test_loopback_is_always_published_and_never_twice():
    assert share.new_manifest(['127.0.0.1', '10.9.8.7'])['bind'] == ['127.0.0.1', '10.9.8.7']


def test_the_share_keeps_clear_of_every_development_port():
    development = {1732, 1733, 1059, 1414, 27017, 27018}
    assert not development & {member.port for member in share.MEMBERS}


def test_a_member_alfred_drives_never_listens_on_the_private_network(monkeypatch):
    monkeypatch.setattr(share.family, 'docker0_address', lambda: None)
    assert share.process_host() == '127.0.0.1'


@pytest.mark.parametrize(
    'pairs, reason',
    [
        (['otto=main'], 'not a member'),
        (['alfred'], 'not MEMBER=VALUE'),
        (['alfred='], 'not MEMBER=VALUE'),
    ],
)
def test_a_member_is_named_as_the_share_runs_it(pairs, reason):
    with pytest.raises(share.Refused, match=reason):
        share.assignments(pairs)


@pytest.mark.parametrize('name', ['ALFRED_DEV_SKIP_AUTH', 'ALFRED_SECRET_KEY'])
def test_the_shares_own_settings_are_not_set_per_member(tmp_path, name):
    share.save(tmp_path, manifest())
    with pytest.raises(share.Refused, match="share's own"):
        share.set_env(SimpleNamespace(member='alfred', setting=f'{name}=1'), tmp_path)


# --- what a share serves ------------------------------------------------------


@pytest.mark.parametrize(
    'facts, said',
    [
        ((COMMIT, COMMIT, COMMIT, True), 'serving'),
        ((COMMIT, COMMIT, '', None), 'not running'),
        ((COMMIT, COMMIT, COMMIT, None), 'unknown: its port does not say what it is'),
        ((COMMIT, COMMIT, COMMIT, False), 'not answering as itself'),
        ((COMMIT, COMMIT, 'b' * 40, True), 'moved, not restarted: ./al share up'),
        (('', '', COMMIT, True), 'not in the manifest'),
    ],
)
def test_a_member_is_serving_only_when_every_fact_agrees(facts, said):
    assert share.verdict(*facts) == said


def git(path, *args):
    subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True)


def repository(tmp_path):
    """An origin with a branch, and the share's clone of it."""
    origin = tmp_path / 'origin.git'
    work = tmp_path / 'work'
    subprocess.run(['git', 'init', '--quiet', '--bare', str(origin)], check=True)
    subprocess.run(['git', 'init', '--quiet', str(work)], check=True)
    for setting in (('user.email', 'test@example.org'), ('user.name', 'Test')):
        git(work, 'config', *setting)
    (work / 'file').write_text('one\n')
    git(work, 'add', 'file')
    git(work, 'commit', '--quiet', '-m', 'one')
    git(work, 'remote', 'add', 'origin', str(origin))
    git(work, 'push', '--quiet', 'origin', 'HEAD:refs/heads/feature')
    clone = tmp_path / 'clone'
    subprocess.run(['git', 'clone', '--quiet', str(origin), str(clone)], check=True)
    return work, clone


def test_a_branch_of_origin_resolves_to_its_commit(tmp_path):
    work, clone = repository(tmp_path)
    expected = subprocess.run(
        ['git', '-C', str(work), 'rev-parse', 'HEAD'], capture_output=True, text=True
    ).stdout.strip()
    assert share.resolve(clone, 'feature') == expected


def test_a_commit_no_branch_of_origin_holds_is_refused(tmp_path):
    _, clone = repository(tmp_path)
    for setting in (('user.email', 'test@example.org'), ('user.name', 'Test')):
        git(clone, 'config', *setting)
    git(clone, 'checkout', '--quiet', '-b', 'local', 'origin/feature')
    (clone / 'file').write_text('two\n')
    git(clone, 'commit', '--quiet', '-am', 'two')
    local = subprocess.run(
        ['git', '-C', str(clone), 'rev-parse', 'HEAD'], capture_output=True, text=True
    ).stdout.strip()
    with pytest.raises(share.Refused, match='on no branch of origin'):
        share.resolve(clone, local)


def test_a_name_that_is_nothing_is_refused(tmp_path):
    _, clone = repository(tmp_path)
    with pytest.raises(share.Refused, match='names no branch'):
        share.resolve(clone, 'no-such-branch')


# --- snapshots ----------------------------------------------------------------


def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(share, 'docker_up', lambda: False)
    share.save(tmp_path, manifest())
    (tmp_path / 'db').mkdir()
    (tmp_path / 'db' / 'collection.wt').write_text('before')
    (tmp_path / 'videos' / '.remote-cache').mkdir(parents=True)
    (tmp_path / 'videos' / 'talk.mp4').write_text('talk')
    (tmp_path / 'videos' / '.remote-cache' / 'fetched.mp4').write_text('fetched')
    return tmp_path


def test_a_snapshot_holds_the_database_the_media_and_the_manifest(tmp_path, monkeypatch):
    state = seeded(tmp_path, monkeypatch)
    assert share.snapshot(SimpleNamespace(name='first'), state) == 0
    taken = state / 'snapshots' / 'first'
    assert (taken / 'db' / 'collection.wt').read_text() == 'before'
    assert (taken / 'videos' / 'talk.mp4').read_text() == 'talk'
    assert not (taken / 'videos' / '.remote-cache').exists()
    held = json.loads((taken / 'manifest.json').read_text())
    assert held['manifest']['members']['alfred']['commit'] == COMMIT


def test_a_snapshot_name_is_taken_once(tmp_path, monkeypatch):
    state = seeded(tmp_path, monkeypatch)
    share.snapshot(SimpleNamespace(name='first'), state)
    with pytest.raises(share.Refused, match='exists'):
        share.snapshot(SimpleNamespace(name='first'), state)


@pytest.mark.parametrize('name', ['../out', '', '.hidden', 'a b'])
def test_a_snapshot_name_stays_inside_the_snapshots(tmp_path, name):
    with pytest.raises(share.Refused, match='not a snapshot name'):
        share.snapshot_dir(tmp_path, name)


def test_a_restore_replaces_the_state_whole(tmp_path, monkeypatch):
    state = seeded(tmp_path, monkeypatch)
    share.snapshot(SimpleNamespace(name='first'), state)
    (state / 'db' / 'collection.wt').write_text('after')
    (state / 'videos' / 'made-later.mp4').write_text('later')
    assert share.restore(SimpleNamespace(name='first', yes=True), state) == 0
    assert (state / 'db' / 'collection.wt').read_text() == 'before'
    assert (state / 'videos' / 'talk.mp4').read_text() == 'talk'
    assert not (state / 'videos' / 'made-later.mp4').exists()


def test_a_restore_without_yes_changes_nothing(tmp_path, monkeypatch):
    state = seeded(tmp_path, monkeypatch)
    share.snapshot(SimpleNamespace(name='first'), state)
    (state / 'videos' / 'made-later.mp4').write_text('later')
    assert share.restore(SimpleNamespace(name='first', yes=False), state) == 1
    assert (state / 'videos' / 'made-later.mp4').exists()


# --- accounts -----------------------------------------------------------------


def test_a_password_goes_to_the_container_on_standard_input(tmp_path, monkeypatch):
    share.save(tmp_path, manifest())
    secret = 'correct horse battery staple'
    asked = {}

    def compose(state, *args, capture=False, stdin=None):
        asked.update(args=args, stdin=stdin)
        return 0, 'made friend@example.org'

    monkeypatch.setattr(share, 'api_container', lambda: 'alfred-share-api-1')
    monkeypatch.setattr(share, 'compose', compose)
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(isatty=lambda: False, readline=lambda: secret + '\n'))
    args = SimpleNamespace(email='friend@example.org', name='Friend', superuser=False)
    assert share.account(args, tmp_path) == 0
    assert asked['stdin'] == secret + '\n'
    assert not any(secret in part for part in asked['args'])


def test_an_account_needs_alfred_running(tmp_path, monkeypatch):
    share.save(tmp_path, manifest())
    monkeypatch.setattr(share, 'api_container', lambda: '')
    args = SimpleNamespace(email='friend@example.org', name='Friend', superuser=False)
    with pytest.raises(share.Refused, match='not running'):
        share.account(args, tmp_path)
