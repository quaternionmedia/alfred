"""The docs account for what the code offers.

Three promises, each one a reader acts on:
- `docs/configuration.md` names every setting alfred reads;
- `docs/family.md` names every setting `./al family` reads;
- every `./al COMMAND` the docs tell someone to type is a command `./al` runs.

None of this is checked by the docs build, which knows pages and links but not
what the code reads. Each failure here is a sentence someone would follow to
a dead end, or a setting nobody can find out about.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SETTING = re.compile(r'(?:ALFRED|OTTO)_[A-Z0-9_]+')
FAMILY_SETTING = re.compile(r'(?:ALFRED_FAMILY|ALFRED_JOE|ALFRED_SMOKE)_[A-Z0-9_]*')

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


def alfreds_settings():
    """What alfred's own modules and otto read, families by their prefix.

    test_stack_settings.py expands the audio-engine contract family into its
    names; a reader is told the family, so the prefix is what must appear.
    """
    package = REPO / 'alfred'
    sources = [
        path
        for path in package.rglob('*.py')
        if path.relative_to(package).parts[0] not in ('otto', 'vox')
    ]
    sources += sorted((package / 'otto' / 'otto').rglob('*.py'))
    return settings_in(sources, SETTING)


def test_the_configuration_page_names_every_setting_alfred_reads():
    page = (REPO / 'docs' / 'configuration.md').read_text(encoding='utf-8')
    settings = alfreds_settings()
    assert len(settings) >= 15, 'found too few settings to be checking anything'
    missing = sorted(name for name in settings if name not in page)
    assert not missing, (
        f'docs/configuration.md does not mention {missing}: a setting nobody '
        'can find out about. Add a row to its table.'
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
