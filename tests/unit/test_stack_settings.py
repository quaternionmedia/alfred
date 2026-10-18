"""Every setting alfred reads reaches the containers that read it.

alfred is configured from the environment, and in a container the environment
is what the compose file hands it: a setting the compose files do not pass does
nothing when it is exported. Ten were in that state, ALFRED_ALLOW_REGISTRATION
among them -- the only way to open registration on a production stack --
documented, exported, and ignored.

The settings are read from the code rather than listed here: every string in
alfred's own modules, and in the engine's, that is a whole ALFRED_* or OTTO_*
name, with the ALFRED_AUDIO_ENGINE_CONTRACT_ family expanded to one name per
field of vox's EngineContract. So a setting added to config.py fails here until
the compose files pass it, or until WITHHELD says why a stack must not.

Unlike test_stack_config.py, these parse the YAML. Each compose file keeps its
settings in one anchored list that both services merge, and only a parser
resolves an anchor. Compose's merge of several files is modelled for the two
keys that matter here, `environment` and `env_file`.
"""

import ast
import dataclasses
import re
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]

SETTING = re.compile(r'(?:ALFRED|OTTO)_[A-Z0-9_]+')
CONTRACT_PREFIX = 'ALFRED_AUDIO_ENGINE_CONTRACT_'

# The stacks a person starts, as `./al` composes them, and which kind each is.
STACKS = {
    'dev': (('docker-compose.yml', 'dev.yml'), 'development'),
    'thin': (('docker-compose.yml', 'dev.yml', 'thin.yml'), 'development'),
    'production': (('docker-compose.yml', 'production.yml'), 'production'),
}
SERVICES = ('api', 'renderer')

# What a kind of stack deliberately does not take from the shell, and why.
WITHHELD = {
    ('development', 'api', 'ALFRED_PRODUCTION'): (
        'a dev stack is not production, however the shell is set up; '
        'production.yml sets it'
    ),
    ('development', 'renderer', 'ALFRED_PRODUCTION'): 'as for the api',
    ('development', 'api', 'ALFRED_SECRET_KEY'): (
        "the api's env files carry it, and a bare name would erase their "
        'value whenever the shell had none (test_the_dev_api_signs_with_...)'
    ),
    ('development', 'renderer', 'ALFRED_SECRET_KEY'): 'the worker signs nothing',
    ('production', 'api', 'ALFRED_DEV_SKIP_AUTH'): (
        'the auth bypass has no way into a production stack'
    ),
    ('production', 'renderer', 'ALFRED_DEV_SKIP_AUTH'): 'as for the api',
    ('production', 'renderer', 'ALFRED_SECRET_KEY'): 'the worker signs nothing',
}

# Where a stack gives a setting a value of its own rather than the shell's.
OWN_VALUES = {
    ('production', 'ALFRED_PRODUCTION'): 'production.yml is the production stack',
    ('production', 'ALFRED_SECRET_KEY'): 'required from the shell, with a reason',
    ('production', 'ALFRED_PUBLIC_URL'): 'the host traefik serves, unless exported',
    ('development', 'OTTO_DOWNLOAD_DIR'): "ALFRED_REMOTE_CACHE_DIR's, by otto's name",
    ('production', 'OTTO_DOWNLOAD_DIR'): "ALFRED_REMOTE_CACHE_DIR's, by otto's name",
}


def string_constants(path):
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


@lru_cache(maxsize=None)
def settings_alfred_reads():
    """Every ALFRED_* and OTTO_* name the code reads, the contract family
    expanded.

    alfred's own modules, and the engine's package for the names it reads
    itself (OTTO_DOWNLOAD_DIR). Not vox: alfred reaches it only through
    `utils.audio_engine`, whose settings are config.py's.
    """
    from vox.contract import EngineContract

    package = REPO / 'alfred'
    sources = [
        path
        for path in package.rglob('*.py')
        if path.relative_to(package).parts[0] not in ('otto', 'vox')
    ]
    sources += sorted((package / 'otto' / 'otto').rglob('*.py'))
    names = {
        value
        for path in sources
        for value in string_constants(path)
        if SETTING.fullmatch(value)
    }
    families = {name for name in names if name.endswith('_')}
    assert families <= {CONTRACT_PREFIX}, (
        f'{sorted(families - {CONTRACT_PREFIX})}: a family of settings read by '
        'prefix, which this test does not know how to list'
    )
    names -= families
    names |= {
        CONTRACT_PREFIX + field.name.upper()
        for field in dataclasses.fields(EngineContract)
    }
    return frozenset(names)


@lru_cache(maxsize=None)
def compose_file(name):
    return yaml.safe_load((REPO / name).read_text(encoding='utf-8')) or {}


def as_mapping(environment):
    """A service's `environment`, list or mapping, as {name: value or None}.

    None is a bare name: the shell's value when it has one, and otherwise
    nothing at all.
    """
    if isinstance(environment, list):
        pairs = (item.partition('=') for item in environment)
        return {name: (value if equals else None) for name, equals, value in pairs}
    return dict(environment or {})


def stack(name):
    """{service: {'environment': ..., 'env_file': [...], 'extra_hosts': {...}}}
    as compose merges the stack's files: environment by name with later files
    winning, env_file entries in order (a later file's value wins there too),
    and extra_hosts together."""
    merged = {}
    for filename in STACKS[name][0]:
        for service, definition in (
            compose_file(filename).get('services') or {}
        ).items():
            definition = definition or {}
            target = merged.setdefault(
                service, {'environment': {}, 'env_file': [], 'extra_hosts': set()}
            )
            target['environment'].update(as_mapping(definition.get('environment')))
            env_files = definition.get('env_file') or []
            if not isinstance(env_files, list):
                env_files = [env_files]
            target['env_file'] += [
                entry if isinstance(entry, str) else entry['path']
                for entry in env_files
            ]
            target['extra_hosts'] |= set(definition.get('extra_hosts') or [])
    return merged


def test_the_settings_are_read_from_the_code():
    """The list the tests below check against is the code's, and not empty.

    A scan that quietly found nothing -- a moved module, a changed spelling --
    would let every other test here pass.
    """
    found = settings_alfred_reads()
    for name in (
        'ALFRED_ALLOW_REGISTRATION',
        'ALFRED_SECRET_KEY',
        'ALFRED_RENDER_DIR',
        'ALFRED_AUDIO_ENGINE_URL',
        'OTTO_DOWNLOAD_DIR',
        CONTRACT_PREFIX + 'MEDIA_UPLOAD',
    ):
        assert name in found, f'the scan of the code did not find {name}'


@pytest.mark.parametrize('service', SERVICES)
@pytest.mark.parametrize('name', STACKS)
def test_every_setting_reaches_the_service(name, service):
    files, kind = STACKS[name]
    environment = stack(name)[service]['environment']
    missing = [
        setting
        for setting in sorted(settings_alfred_reads())
        if setting not in environment and (kind, service, setting) not in WITHHELD
    ]
    assert not missing, (
        f'The {name} stack ({" + ".join(files)}) never hands the {service} '
        f'{missing}. alfred reads them, so exporting one does nothing. Add each '
        "to the x-alfred-settings list the file's api and renderer merge, or "
        'to WITHHELD here with the reason it must not be passed.'
    )


@pytest.mark.parametrize('name', STACKS)
def test_what_is_withheld_stays_out(name):
    """WITHHELD is a rule, not an excuse: the stack really does not pass it."""
    kind = STACKS[name][1]
    merged = stack(name)
    passed = [
        f'{service}: {setting} ({reason})'
        for (of, service, setting), reason in WITHHELD.items()
        if of == kind and setting in merged[service]['environment']
    ]
    assert not passed, f'The {name} stack passes what it must not: {passed}'


@pytest.mark.parametrize('name', STACKS)
def test_a_setting_arrives_as_the_shell_has_it(name):
    """Passed through, not given a default here.

    A bare name hands over the shell's value, or leaves the setting unset so
    the code's own default holds. `${NAME:-}` would hand over an empty string
    instead, which is not the default for every setting: an empty
    ALFRED_RENDER_DIR or ALFRED_DELIVERY_DIR is the working directory, and an
    empty ALFRED_DEV_USER_EMAIL is nobody. OWN_VALUES lists the few a stack
    sets itself.
    """
    kind = STACKS[name][1]
    merged = stack(name)
    given = []
    for service in SERVICES:
        environment = merged[service]['environment']
        for setting in sorted(settings_alfred_reads()):
            value = environment.get(setting)
            if value is not None and (kind, setting) not in OWN_VALUES:
                given.append(f'{service}: {setting}={value!r}')
    assert not given, (
        f'The {name} stack sets these rather than passing the shell\'s: '
        f'{given}. Pass the bare name, or add it to OWN_VALUES with the reason.'
    )


@pytest.mark.parametrize('name', STACKS)
def test_the_api_and_the_renderer_get_the_same_settings(name):
    """One list per file, merged into both, so they cannot drift apart.

    Except the signing key, which only the api uses.
    """
    merged = stack(name)

    def settings_of(service):
        environment = merged[service]['environment']
        return {
            setting: environment[setting]
            for setting in settings_alfred_reads()
            if setting in environment and setting != 'ALFRED_SECRET_KEY'
        }

    api, renderer = settings_of('api'), settings_of('renderer')
    differing = sorted(k for k in api.keys() & renderer.keys() if api[k] != renderer[k])
    assert api == renderer, (
        f'The {name} stack gives its api and renderer different settings: '
        f'only the api {sorted(api.keys() - renderer.keys())}, only the '
        f'renderer {sorted(renderer.keys() - api.keys())}, different values '
        f'for {differing}.'
    )


@pytest.mark.parametrize('name', STACKS)
def test_every_name_passed_is_one_alfred_reads(name):
    """A misspelt setting passes nothing, and says nothing about it."""
    merged = stack(name)
    stray = sorted(
        {
            setting
            for service in SERVICES
            for setting in merged[service]['environment']
            if SETTING.fullmatch(setting) and setting not in settings_alfred_reads()
        }
    )
    assert not stray, (
        f'The {name} stack passes {stray}, which alfred does not read: a typo, '
        'or a setting the code no longer has.'
    )


@pytest.mark.parametrize('name', ['dev', 'thin'])
def test_the_dev_api_signs_with_this_checkouts_key(name):
    """ALFRED_SECRET_KEY reaches the dev api from its env files, and only
    from them.

    docker-compose.yml loads the committed stub (`.secret_key`, an empty key)
    and dev.yml then `.secret_key.local`, which `./al` creates with a random
    key, so the checkout's own key wins. A bare ALFRED_SECRET_KEY in
    `environment` would not add the shell's key to that: compose takes a bare
    name as "the shell's value, or none", and a name the shell does not set is
    removed -- along with the key the env files gave it.
    """
    api = stack(name)['api']
    env_files = api['env_file']
    assert '.secret_key.local' in env_files and '.secret_key' in env_files
    assert env_files.index('.secret_key.local') > env_files.index(
        '.secret_key'
    ), ".secret_key.local must load after the stub, or the stub's empty key wins"
    assert 'ALFRED_SECRET_KEY' not in api['environment'], (
        'ALFRED_SECRET_KEY is in the dev api\'s environment, which overrides '
        'its env files -- and a bare name the shell does not set erases them'
    )


@pytest.mark.parametrize('service', SERVICES)
@pytest.mark.parametrize('name', ['dev', 'production'])
def test_the_documented_engine_address_resolves_on_a_linux_host(name, service):
    """host.docker.internal is mapped to the host, for both services.

    The docs point ALFRED_AUDIO_ENGINE_URL at http://host.docker.internal:8010,
    an engine running beside the stack. Docker Desktop provides that name and
    a Linux host does not, so without the mapping the address resolves on a
    laptop and nowhere else -- on a Linux host the api and the worker would
    each report the engine unreachable. The api checks it for /health and
    analysis, and the worker transcribes, so both need it.
    """
    assert 'host.docker.internal:host-gateway' in stack(name)[service]['extra_hosts'], (
        f'The {name} {service} does not map host.docker.internal to the host '
        '(extra_hosts: host.docker.internal:host-gateway).'
    )


# --- where the stacks listen ----------------------------------------------

COMPOSE_FILES = [
    'docker-compose.yml',
    'dev.yml',
    'thin.yml',
    'production.yml',
    'pytest.yml',
    'flower.yml',
    'test_e2e.yml',
]

# A published port's address: loopback, or what ALFRED_BIND (ALFRED_DB_BIND
# for the database) says, defaulting to loopback.
LOOPBACK_BY_DEFAULT = re.compile(
    r'^(?:127\.0\.0\.1|\$\{ALFRED_(?:DB_)?BIND:-127\.0\.0\.1\}):'
)


@pytest.mark.parametrize('filename', COMPOSE_FILES)
def test_nothing_is_published_beyond_this_machine_by_default(filename):
    """Every published port names its address, and it is loopback unless the
    person starting the stack says otherwise.

    A port written as `5555:5555` is published on every interface. flower.yml
    did that, and flower asks for no login and can shut workers down; the
    dev stack did it too, until ALFRED_BIND, and with the auth bypass on that
    served every request on the network as a superuser.
    """
    published = [
        (service, port)
        for service, definition in (
            compose_file(filename).get('services') or {}
        ).items()
        for port in (definition or {}).get('ports') or []
    ]
    open_ = [
        f'{service}: {port!r}'
        for service, port in published
        if not (isinstance(port, str) and LOOPBACK_BY_DEFAULT.match(port))
    ]
    assert not open_, (
        f'{filename} publishes {open_} beyond this machine by default. Name the '
        "address: '${ALFRED_BIND:-127.0.0.1}:<port>:<port>'."
    )


def test_the_docs_server_listens_on_loopback_by_default():
    """`./al docs` serves on loopback unless ALFRED_BIND says otherwise.

    It ran `mkdocs serve -a 0.0.0.0:4000`, so the checkout's docs, drafts
    included, were on the network whenever they were being written.
    """
    lines = [
        line.strip()
        for line in (REPO / 'al').read_text(encoding='utf-8').splitlines()
        if 'mkdocs serve' in line and not line.strip().startswith('#')
    ]
    assert lines, './al no longer runs `mkdocs serve`; update this test'
    for line in lines:
        assert '"${ALFRED_BIND:-127.0.0.1}:' in line, (
            f'./al serves the docs with {line!r}: bind '
            '"${ALFRED_BIND:-127.0.0.1}:4000"'
        )


# --- the browser suite's stack ---------------------------------------------

E2E_OUTPUTS = (
    'ALFRED_RENDER_DIR',
    'ALFRED_DELIVERY_DIR',
    'ALFRED_PREVIEW_DIR',
    'OTTO_DOWNLOAD_DIR',
)


def e2e_service(service):
    return compose_file('test_e2e.yml')['services'][service]


def mounted_at(service, path):
    """(source, target) of the mount `path` is on in an e2e service: the one
    whose target is the longest prefix of it."""
    mounts = []
    for volume in e2e_service(service).get('volumes') or []:
        source, target = volume.split(':')[:2]
        target = target.rstrip('/') or '/'
        if path == target or path.startswith(target.rstrip('/') + '/'):
            mounts.append((source, target))
    assert mounts, f'{path} is on no mount of the e2e {service}'
    return max(mounts, key=lambda mount: len(mount[1]))


@pytest.mark.parametrize('service', SERVICES)
def test_the_browser_suite_takes_nothing_from_the_shell(service):
    """Its settings are fixed in test_e2e.yml, so a run tests the same stack
    on every machine, whatever the shell running it exports."""
    environment = as_mapping(e2e_service(service).get('environment'))
    borrowed = sorted(
        name
        for name, value in environment.items()
        if value is None or '$' in str(value)
    )
    assert not borrowed, f'the e2e {service} takes {borrowed} from the shell'


@pytest.mark.parametrize('setting', E2E_OUTPUTS)
@pytest.mark.parametrize('service', SERVICES)
def test_what_the_browser_suite_makes_is_kept_off_the_checkout(service, setting):
    """Renders, deliveries, preview frames and fetched media go to a volume
    of the stack's own, not through the repository mount into the checkout.

    With the defaults the e2e renders landed in the working tree's
    videos/renders/ and its local deliveries in deliveries/, where the dev
    stack listed them as orphans.
    """
    environment = as_mapping(e2e_service(service).get('environment'))
    path = environment.get(setting)
    assert path, f'the e2e {service} does not set {setting}, so it writes the default'
    source, _ = mounted_at(service, path)
    declared = compose_file('test_e2e.yml').get('volumes') or {}
    assert source in declared, (
        f"The e2e {service}'s {setting} is {path}, on the mount of {source!r} -- "
        'not a volume test_e2e.yml declares, so the output lands outside the '
        'stack: in the checkout, for the repository mount.'
    )


@pytest.mark.parametrize('setting', ['ALFRED_RENDER_DIR', 'OTTO_DOWNLOAD_DIR'])
def test_the_api_and_the_renderer_find_each_others_files(setting):
    """The worker writes a render where the api looks for it, and one fetch of
    remote media serves both: same path, same volume."""
    api = as_mapping(e2e_service('api').get('environment'))[setting]
    renderer = as_mapping(e2e_service('renderer').get('environment'))[setting]
    assert api == renderer, f'{setting}: the api has {api}, the renderer {renderer}'
    assert mounted_at('api', api) == mounted_at('renderer', renderer)
