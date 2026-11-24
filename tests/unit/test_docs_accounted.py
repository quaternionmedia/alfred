"""The docs account for what the code offers.

Three promises, each one a reader acts on:
- `docs/configuration.md` names every setting alfred reads, and every one the
  compose files and `./al` read on the host;
- `docs/family.md` names every setting `./al family` reads;
- every `./al COMMAND` the docs tell someone to type is a command `./al` runs.

None of this is checked by the docs build, which knows pages and links but not
what the code reads. Each failure here is a sentence someone would follow to
a dead end, or a setting nobody can find out about.

A setting is found by how it is read, not by its name. Looking for `ALFRED_`
and `OTTO_` names alone passed over the database, broker and mail settings,
which the page did account for, and over `LOG_DIR`, `UID`, `GID` and
`COMPOSE_PROJECT_NAME`, which it did not.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SETTING = re.compile(r'(?:ALFRED|OTTO)_[A-Z0-9_]+')
FAMILY_SETTING = re.compile(r'(?:ALFRED_FAMILY|ALFRED_JOE|ALFRED_SMOKE)_[A-Z0-9_]*')
NAME = re.compile(r'[A-Z][A-Z0-9_]*')
# The names a mapping of the environment goes by in alfred and otto:
# `environ`, `os.environ`, and `env`, the argument config.py's helpers take.
ENVIRONMENT = {'environ', 'env'}

# The documents a person reads to learn a command or a setting.
DOCUMENTS = (
    ['README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'tests/README.md']
    + [str(path.relative_to(REPO)) for path in sorted((REPO / 'docs').rglob('*.md'))]
    + ['website/e2e/README.md']
)
# Generated from the specs, and quotes recipes rather than instructing.
NOT_INSTRUCTIONS = {'docs/cookbook.md'}


def string_constants(path):
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def settings_in(paths, pattern):
    return {
        value
        for path in paths
        for value in string_constants(path)
        if pattern.fullmatch(value)
    }


def is_environment(node):
    if isinstance(node, ast.Name):
        return node.id in ENVIRONMENT
    return isinstance(node, ast.Attribute) and node.attr == 'environ'


def environment_reads(path):
    """The names `path` looks up in the environment, whatever they are.

    `environ.get(NAME)`, `environ[NAME]` and `getenv(NAME)`, with NAME a
    string or a module-level name for one (otto's `DOWNLOAD_DIR_ENV`); and a
    string handed to a helper along with the environment, as in
    `resolve_seconds(environ, 'ALFRED_FRAME_TTL', 3600)`.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    named = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    def text(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return named.get(node.id)
        return None

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and is_environment(node.value):
            found.append(text(node.slice))
        elif isinstance(node, ast.Call):
            call = node.func
            called = getattr(call, 'attr', getattr(call, 'id', ''))
            if called == 'getenv' or (
                called in ('get', 'setdefault', 'pop') and is_environment(call.value)
            ):
                found.extend(text(arg) for arg in node.args[:1])
            elif any(is_environment(arg) for arg in node.args):
                found.extend(text(arg) for arg in node.args)
    return {name for name in found if name and NAME.fullmatch(name)}


def alfreds_settings():
    """What alfred's own modules and otto read: every name they look up in the
    environment, and the ALFRED_ and OTTO_ names they build lookups from.

    test_stack_settings.py expands the audio-engine contract family into its
    names; a reader is told the family, so the prefix is what must appear.

    vox is left out. alfred loads its contract and media client, which read
    nothing from the environment, and configures them from its own settings;
    vox's one setting, VOX_OUTPUT_DEVICE, belongs to a speech adapter alfred
    never loads.
    """
    package = REPO / 'alfred'
    sources = [
        path
        for path in package.rglob('*.py')
        if path.relative_to(package).parts[0] not in ('otto', 'vox')
    ]
    sources += sorted((package / 'otto' / 'otto').rglob('*.py'))
    found = settings_in(sources, SETTING)
    for path in sources:
        found |= environment_reads(path)
    return found


def host_settings():
    """What is read on the host: each name a compose file interpolates
    (`${ALFRED_PORT:-8000}`), and each `./al` reads with a default, the way
    it reads what the shell may set (`${ALFRED_BIND:-127.0.0.1}`)."""
    found = set()
    for path in sorted(REPO.glob('*.yml')):
        text = path.read_text(encoding='utf-8')
        found |= set(re.findall(r'(?<!\$)\$\{([A-Z][A-Z0-9_]*)', text))
    al = (REPO / 'al').read_text(encoding='utf-8')
    found |= set(re.findall(r'\$\{([A-Z][A-Z0-9_]*):?[-=?+]', al))
    return found


def mentions(page, name):
    """Whether `page` names `name` as itself, not inside a longer name."""
    return re.search(rf'(?<![A-Z0-9_]){re.escape(name)}(?![A-Z0-9])', page) is not None


def test_the_configuration_page_names_every_setting_alfred_reads():
    page = (REPO / 'docs' / 'configuration.md').read_text(encoding='utf-8')
    settings = alfreds_settings()
    assert len(settings) >= 15, 'found too few settings to be checking anything'
    # Found by how they are read: none of these is an ALFRED_ or OTTO_ name.
    assert {'DB_URL', 'EMAIL_PASSWORD', 'VIDEO_DIR', 'STATIC_DIR'} <= settings
    missing = sorted(name for name in settings if not mentions(page, name))
    assert not missing, (
        f'docs/configuration.md does not mention {missing}: a setting nobody '
        'can find out about. Add a row to its table, or name it with the '
        'plumbing.'
    )


def test_the_configuration_page_names_every_setting_read_on_the_host():
    page = (REPO / 'docs' / 'configuration.md').read_text(encoding='utf-8')
    settings = host_settings()
    assert {'ALFRED_PORT', 'ALFRED_DB_BIND', 'COMPOSE_PROJECT_NAME'} <= settings
    missing = sorted(name for name in settings if not mentions(page, name))
    assert not missing, (
        f'docs/configuration.md does not mention {missing}, which the compose '
        'files or ./al read from the shell. Add a row to its table.'
    )


def test_the_family_page_names_every_setting_the_helper_reads():
    page = (REPO / 'docs' / 'family.md').read_text(encoding='utf-8')
    script = REPO / 'scripts' / 'family.py'
    names = settings_in([script], FAMILY_SETTING)
    # The per-repository settings are built from each name, not written out.
    names |= {
        'ALFRED_FAMILY_' + re.sub(r'[^A-Z0-9]', '_', name.upper())
        for name in re.findall(
            r"Repo\(\s*'([a-z0-9-]+)'", script.read_text(encoding='utf-8')
        )
        if name != 'alfred'
    }
    assert {'ALFRED_FAMILY_JOE', 'ALFRED_JOE_PORT', 'ALFRED_SMOKE_EMAIL'} <= names
    missing = sorted(name for name in names if name not in page)
    assert not missing, f'docs/family.md does not mention {missing}'


def commands_al_runs():
    names = set()
    for line in (REPO / 'al').read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith(('if ', 'elif ')):
            names |= set(re.findall(r'\$1 = "([^"]+)"', stripped))
    return names


def test_every_command_the_docs_give_is_one_al_runs():
    runs = commands_al_runs()
    assert 'family' in runs and 'dev' in runs
    wrong = []
    for name in DOCUMENTS:
        if name in NOT_INSTRUCTIONS:
            continue
        text = (REPO / name).read_text(encoding='utf-8')
        for command in re.findall(r'\./al\s+([a-z][a-z0-9-]*)', text):
            if command not in runs:
                wrong.append(f'{name}: ./al {command}')
    assert (
        not wrong
    ), f'the docs tell someone to run commands ./al does not have: {sorted(set(wrong))}'
