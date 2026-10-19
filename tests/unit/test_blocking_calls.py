"""No coroutine in the api calls a known-blocking function directly.

The api is one process with one event loop, and a coroutine that calls
something blocking holds every other request until it returns. The previews,
the demo media, the queue sends, the mail and the library listing all did
(tests/unit/test_event_loop.py). This reads alfred's own source -- every module
under `alfred/` except the two vendored engines -- and fails, naming the
coroutine, the line and the call, when an `async def` calls something in
BLOCKING directly, or calls a function of alfred's own that does, at any depth.

How a call is read:

- Names are followed through imports: aliases (`from subprocess import run as
  bash` is `subprocess.run`), relative imports, and the packages that re-export
  a name (`from ..utils import sendMail` is `alfred.core.utils.email.sendMail`).
- A plain function of alfred's own blocks when its body calls something that
  blocks. That is worked out across modules, so a helper that runs ffmpeg is
  caught where a coroutine calls the helper.
- A method cannot be followed, since the scan does not know what object it is
  called on. The few method names that block wherever alfred calls them are in
  BLOCKING_METHODS.
- What a coroutine hands to the thread pool is a value, not a call, and so is
  not counted: `run_in_threadpool(generate_clip, path)`, and a lambda.

Its limits, and what covers each:

- A call made through something the scan cannot see into is invisible: a
  dependency FastAPI injects (`queue=Depends(get_render_queue)` is Celery's
  `delay`), a method outside BLOCKING_METHODS (`self.password_helper.hash`), a
  function passed in as an argument. test_event_loop.py checks each queue
  send, injected as it is, one by one.
- Only alfred's own code is read. A library coroutine that blocks inside itself
  is not seen: fastapi-users hashes passwords inline in `authenticate`.
- A function or lambda defined inside a coroutine is not counted against it,
  as it is almost always what goes to the thread pool. One that the coroutine
  calls directly is missed.
- Looking up one file is not listed: `os.stat`, `isfile`, `realpath`. That
  costs microseconds on a local disk, and the routes that serve a file do it a
  few times each. Listing a directory is listed.
- Work done in alfred's own Python has no name to list. Parsing a subtitle
  file took most of a second at its size limit; measuring found that, and
  this would not have.
- Only `async def` is checked. A plain `def` route runs in FastAPI's thread
  pool, where blocking is what it is for.

The lists name what alfred calls. When the api starts calling something new
that blocks, add it.
"""

import ast
import os
from pathlib import Path
from textwrap import dedent

import pytest

# Where the scan starts, found from here rather than by importing the app: the
# source is read, never run. The vendored engines below it are not alfred's.
ROOT = Path(__file__).resolve().parents[2] / 'alfred'
VENDORED = ('otto', 'vox')

BLOCKING = {
    # A process, waited for.
    'subprocess.run': 'starts a process and waits for it',
    'subprocess.call': 'starts a process and waits for it',
    'subprocess.check_call': 'starts a process and waits for it',
    'subprocess.check_output': 'starts a process and waits for it',
    'os.system': 'starts a process and waits for it',
    'time.sleep': 'sleeps',
    # The network, synchronously.
    'requests.get': 'makes an HTTP request',
    'requests.head': 'makes an HTTP request',
    'requests.post': 'makes an HTTP request',
    'requests.request': 'makes an HTTP request',
    'urllib.request.urlopen': 'makes an HTTP request',
    'smtplib.SMTP': 'talks to a mail server',
    'google.cloud.storage.Client': 'talks to Google Cloud Storage',
    'alfred.core.utils.audio_engine._call': 'asks the audio engine, over HTTP',
    # The broker, through Celery's control API.
    'alfred.core.utils.tasks.worker_count': 'pings the render workers',
    'alfred.core.utils.tasks.pending_count': 'asks the broker',
    # The database, synchronously: every query on the handle blocks.
    'alfred.core.utils.db.get_sync_db': 'queries the synchronous database client',
    # Whole directories and files.
    'os.listdir': 'lists a directory',
    'os.scandir': 'lists a directory',
    'os.walk': 'walks a directory tree',
    'shutil.copyfile': 'copies a whole file',
    'shutil.copy': 'copies a whole file',
    'shutil.copy2': 'copies a whole file',
    'shutil.move': 'moves a file, copying it across devices',
    'shutil.rmtree': 'removes a directory tree',
    # The engine, building or writing media.
    'otto.render.generateEdl': 'builds a timeline: opens and decodes its media',
    'otto.render.renderFrame': 'builds a timeline, and draws and encodes a frame',
    'otto.render.renderMultitrack': 'renders a video',
    'otto.render.renderSound': "writes a timeline's sound",
    'otto.media.probe': 'runs ffmpeg to describe a file',
    'otto.demo.demoClip': 'runs ffmpeg to write a clip',
}

BLOCKING_METHODS = {
    'save_frame': 'draws and encodes a frame',
    'write_videofile': 'encodes a video',
    'write_audiofile': 'encodes sound',
    'delay': 'sends a job to the broker',
    'apply_async': 'sends a job to the broker',
    'deliver': 'copies or uploads a whole render',
}


class Module:
    """One module's source, read: its imports and its own top-level functions."""

    def __init__(self, name, source, package=False, path=None):
        self.name = name
        self.path = path or name
        self.tree = ast.parse(source)
        self.package = name if package else name.rpartition('.')[0]
        self.imports = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        self.imports[alias.asname] = alias.name
                    else:
                        head = alias.name.split('.')[0]
                        self.imports[head] = head
            elif isinstance(node, ast.ImportFrom):
                base = self._absolute(node.module, node.level)
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = f'{base}.{alias.name}'
        self.functions = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def _absolute(self, module, level):
        if not level:
            return module
        parts = self.package.split('.')
        base = '.'.join(parts[: len(parts) - (level - 1)])
        return f'{base}.{module}' if module else base


def dotted(expression):
    """`a.b.c` for a name or a chain of attributes on one; None otherwise."""
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        base = dotted(expression.value)
        return f'{base}.{expression.attr}' if base else None
    return None


def own_calls(function):
    """The calls in a function's body, but not in what it defines itself."""
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            continue
        if isinstance(node, ast.Call):
            yield node
        pending.extend(ast.iter_child_nodes(node))


class Scan:
    """Every module, every alfred function that blocks, and why."""

    def __init__(self, modules):
        self.modules = {module.name: module for module in modules}
        self.functions = {
            f'{module.name}.{name}': (module, node)
            for module in modules
            for name, node in module.functions.items()
        }
        # A blocking alfred function -> the calls down to what blocks.
        self.blocking = {}
        found = True
        while found:
            found = False
            for name, (module, node) in self.functions.items():
                if name in self.blocking or isinstance(node, ast.AsyncFunctionDef):
                    continue
                for call in own_calls(node):
                    why = self.why(module, call)
                    if why:
                        self.blocking[name] = why
                        found = True
                        break

    def resolve(self, module, name):
        """What `name`, as written in `module`, refers to."""
        head, _, rest = name.partition('.')
        if head in module.imports:
            target = module.imports[head]
        elif head in module.functions:
            target = f'{module.name}.{head}'
        else:
            return name
        return self.canonical(f'{target}.{rest}' if rest else target)

    def canonical(self, name):
        """`name`, followed through the packages that re-export it."""
        for _ in range(10):
            parts = name.split('.')
            for cut in range(len(parts) - 1, 0, -1):
                module = self.modules.get('.'.join(parts[:cut]))
                if module is None:
                    continue
                first, rest = parts[cut], parts[cut + 1 :]
                if first in module.imports and first not in module.functions:
                    name = '.'.join([module.imports[first], *rest])
                    break
                return name
            else:
                return name
        return name

    def why(self, module, call):
        """The chain of calls by which `call` blocks, or None."""
        name = dotted(call.func)
        if name is not None:
            target = self.resolve(module, name)
            if target in BLOCKING:
                return [f'{target} ({BLOCKING[target]})']
            if target in self.blocking:
                return [target, *self.blocking[target]]
            if target in self.functions:
                return None
        if isinstance(call.func, ast.Attribute):
            method = call.func.attr
            if method in BLOCKING_METHODS:
                return [f'.{method}() ({BLOCKING_METHODS[method]})']
        return None

    def violations(self):
        """Each direct call in a coroutine to something that blocks, in the
        order of the source."""
        found = []
        for module in self.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.AsyncFunctionDef):
                    continue
                for call in own_calls(node):
                    why = self.why(module, call)
                    if why:
                        found.append((module.path, call.lineno, node.name, why))
        return [
            f'{path}:{line} {coroutine}() calls ' + ' -> '.join(why)
            for path, line, coroutine, why in sorted(found)
        ]


def alfred_modules(root=ROOT):
    """alfred's own modules, read from `root`."""
    modules = []
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not (Path(directory) == root and name in VENDORED)
            and name != '__pycache__'
        )
        for file in sorted(f for f in files if f.endswith('.py')):
            path = Path(directory) / file
            relative = path.relative_to(root.parent)
            parts = list(relative.with_suffix('').parts)
            package = parts[-1] == '__init__'
            if package:
                parts.pop()
            modules.append(
                Module(
                    '.'.join(parts),
                    path.read_text(encoding='utf-8'),
                    package=package,
                    path=relative.as_posix(),
                )
            )
    return modules


@pytest.fixture(scope='module')
def api():
    return Scan(alfred_modules())


class TestTheApi:
    def test_no_coroutine_calls_anything_that_blocks(self, api):
        found = api.violations()
        assert not found, (
            'A coroutine calls something that blocks, and every request waits '
            'while it runs. Make the route a plain def (it awaits nothing), or '
            'hand the call to run_in_threadpool:\n' + '\n'.join(found)
        )

    def test_the_scan_reads_the_api(self, api):
        """A scan that read nothing would pass. These are coroutines it must
        have read, and helpers it must see block through other modules."""
        coroutines = {
            node.name
            for module in api.modules.values()
            for node in ast.walk(module.tree)
            if isinstance(node, ast.AsyncFunctionDef)
        }
        routes_and_hooks = {'healthz', 'previewFrameFile', 'queueRender', 'checkFonts'}
        assert routes_and_hooks <= coroutines
        helpers = {
            'alfred.core.routes.demo.generate_clip',
            'alfred.core.routes.preview.sweep_frames',
            'alfred.core.utils.probe.probe',
            'alfred.core.utils.email.sendMail',
            'alfred.core.utils.media.library_files',
            'alfred.core.utils.audio_engine.analyze',
            'alfred.core.utils.bucket.signed_url',
        }
        assert helpers <= set(api.blocking)


def scan(source):
    """What the scan finds in one module made up for a test."""
    return Scan([Module('alfred.made_up', dedent(source))]).violations()


class TestTheScan:
    """What it catches and what it lets be, in modules made up for it."""

    def test_a_coroutine_that_starts_a_process(self):
        found = scan(
            '''
            import subprocess
            async def route():
                subprocess.run(['ffmpeg'])
            '''
        )
        assert found == [
            'alfred.made_up:4 route() calls subprocess.run '
            '(starts a process and waits for it)'
        ]

    def test_through_an_alias(self):
        found = scan(
            '''
            from subprocess import run as bash
            async def hook():
                bash(['fc-list'])
            '''
        )
        assert found == [
            'alfred.made_up:4 hook() calls subprocess.run '
            '(starts a process and waits for it)'
        ]

    def test_through_a_helper_another_package_re_exports(self):
        package = Module('alfred.utils', 'from .email import send\n', package=True)
        helper = Module(
            'alfred.utils.email',
            dedent(
                '''
                from smtplib import SMTP
                def send(to):
                    SMTP('mail').send_message(to)
                '''
            ),
        )
        route = Module(
            'alfred.routes.issue',
            dedent(
                '''
                from ..utils import send
                async def report():
                    send('support')
                '''
            ),
        )
        assert Scan([package, helper, route]).violations() == [
            'alfred.routes.issue:4 report() calls alfred.utils.email.send -> '
            'smtplib.SMTP (talks to a mail server)'
        ]

    def test_a_method_known_to_block(self):
        found = scan(
            '''
            async def route(video):
                video.save_frame('frame.jpg')
            '''
        )
        assert found == [
            'alfred.made_up:3 route() calls .save_frame() (draws and encodes a frame)'
        ]

    def test_handing_it_to_the_thread_pool_is_not_calling_it(self):
        found = scan(
            '''
            import subprocess
            from starlette.concurrency import run_in_threadpool
            def make(path):
                subprocess.run(['ffmpeg', path])
            async def route():
                await run_in_threadpool(make, 'a')
                await run_in_threadpool(lambda: make('b'))
            '''
        )
        assert found == []

    def test_a_plain_function_route_may_block(self):
        found = scan(
            '''
            import subprocess
            def route():
                subprocess.run(['ffmpeg'])
            '''
        )
        assert found == []
