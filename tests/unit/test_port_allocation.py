"""alfred's default ports are the ones qm's port allocation gives it.

qm's dashboard (`governance/qm/ci/dashboard.py`) gives each QM surface one
fixed port, the first four digits of a constant: alfred root three, and joe,
which alfred reaches for sound, the twelfth root of two. alfred restates both
numbers as its defaults, in a repository that does not import qm's tooling,
and a number copied across a seam stays true only while something checks it.
So this reads the allocation's source as a tree, never importing it, and fails
when the two disagree.

Each test skips, saying so, while the vendored allocation names no surface for
its repository: the submodule's pin can predate the surface.
"""

import ast
import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO = Path(__file__).resolve().parents[2]
DASHBOARD = REPO / 'governance' / 'qm' / 'ci' / 'dashboard.py'


def load(name):
    sys.path.insert(0, str(REPO / 'scripts'))
    spec = importlib.util.spec_from_file_location(name, REPO / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


family = load('family')
loop = load('loop')


def allocated(repo):
    """The ports the allocation gives `repo`: each call in it naming `repo=`
    and `port=`. Skips when it names no surface for `repo`."""
    dashboard = DASHBOARD
    if not dashboard.is_file():
        pytest.skip(f'{dashboard} is not checked out, so the allocation is unread')
    tree = ast.parse(dashboard.read_text(encoding='utf-8'), filename=str(dashboard))
    surfaces = [
        {k.arg: k.value for k in node.keywords if k.arg}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ]
    named = [
        given
        for given in surfaces
        if isinstance(given.get('repo'), ast.Constant) and given['repo'].value == repo
    ]
    if not named:
        pytest.skip(
            f"qm's port allocation names no {repo} surface yet, at the pinned "
            f'{dashboard.name}: nothing to agree with until the pin moves'
        )
    ports = {
        given['port'].value
        for given in named
        if isinstance(given.get('port'), ast.Constant)
        and isinstance(given['port'].value, int)
    }
    assert ports, (
        f'{dashboard.name} names a {repo} surface with no port=<number>; '
        'this check needs updating to read it'
    )
    return ports


def api_defaults():
    """Every place alfred writes its api's default host port."""
    al = (REPO / 'al').read_text(encoding='utf-8')
    dev = (REPO / 'dev.yml').read_text(encoding='utf-8')
    found = {
        './al': re.search(r'ALFRED_PORT="\$\{ALFRED_PORT:-(\d+)\}"', al),
        'dev.yml': re.search(r'\$\{ALFRED_PORT:-(\d+)\}:80\b', dev),
    }
    missing = sorted(where for where, match in found.items() if not match)
    assert not missing, f'no ALFRED_PORT default found in {missing}; update this'
    defaults = {where: int(match.group(1)) for where, match in found.items()}
    defaults['./al family'] = urlsplit(family.alfred_base({})).port
    defaults['./al loop'] = loop.Run('main', root=REPO, env={}).port
    return defaults


def test_alfred_serves_on_the_port_qm_allocates_it():
    """Mutation: move the default in any one place, or alfred's surface in the
    allocation, and this fails."""
    ports = allocated('alfred')
    wrong = {where: port for where, port in api_defaults().items() if port not in ports}
    assert not wrong, (
        f"qm's port allocation gives alfred {sorted(ports)}, and these default "
        f'to another port: {wrong}'
    )


def test_alfred_reaches_joe_on_the_port_qm_allocates_it():
    """Mutation: move ALFRED_JOE_PORT's default, or joe's surface, and this
    fails."""
    ports = allocated('joe')
    assert family.joe_port({}) in ports, (
        f"qm's port allocation gives joe {sorted(ports)}, and ./al family "
        f'starts and reaches it on {family.joe_port({})}'
    )
