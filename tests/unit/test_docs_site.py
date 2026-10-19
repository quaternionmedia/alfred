"""What the docs site's build checks.

mkdocs can report a page left out of the nav, a link to no page or file, an
anchor no heading makes, and an absolute link -- each at the level mkdocs.yml
gives it, and most of them at `info` by default, which nobody reads. Two
pages sat outside the nav for years that way. These hold every check at
`warn`, and the docs workflow's build at `--strict`, which makes a warning
fatal before mike deploys anything.
"""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


class _Loader(yaml.SafeLoader):
    """mkdocs.yml may carry mkdocs' own tags (`!ENV`, `!!python/name:`).

    Read as nothing, so a tag added later fails the assertion it affects
    rather than every test here with a ConstructorError.
    """


_Loader.add_multi_constructor('!', lambda loader, suffix, node: None)
_Loader.add_multi_constructor(
    'tag:yaml.org,2002:python/', lambda loader, suffix, node: None
)


def load(relative):
    return yaml.load((REPO / relative).read_text(encoding='utf-8'), Loader=_Loader)


class TestTheBuildChecksEverything:
    CHECKS = [
        'omitted_files',
        'not_found',
        'absolute_links',
        'unrecognized_links',
        'anchors',
    ]

    def test_every_check_mkdocs_makes_is_a_warning(self):
        validation = load('mkdocs.yml').get('validation') or {}
        weaker = {
            check: validation.get(check, 'the default')
            for check in self.CHECKS
            if validation.get(check) != 'warn'
        }
        assert not weaker, (
            f'mkdocs.yml leaves {weaker}; set each to `warn` under '
            '`validation:`, so the strict build in CI fails on it'
        )

    def test_ci_builds_strictly_before_it_deploys(self):
        workflow = load('.github/workflows/docs.yml')
        # PyYAML reads the bare key `on` as the boolean true.
        triggers = workflow.get('on', workflow.get(True)) or {}
        jobs = workflow['jobs']
        commands = [
            line.strip()
            for step in jobs['build']['steps']
            for line in step.get('run', '').split('\n')
        ]
        assert 'mkdocs build --strict' in commands, (
            'the docs workflow must build with --strict: a warning is otherwise '
            'printed and the site deployed anyway'
        )
        assert 'pull_request' in triggers, (
            'build the docs on pull requests, so a broken link is found before '
            'it is merged rather than by the deploy'
        )
        needs = jobs['deploy'].get('needs')
        assert needs == 'build', 'the deploy must need the strict build'
        condition = jobs['deploy'].get('if')
        assert (
            condition == "github.event_name == 'push'"
        ), 'deploy from pushes only: a pull request builds, and never publishes'
