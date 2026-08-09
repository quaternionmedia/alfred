"""The template allowlist, and what it protects.

`Bin.js` has always requested a template list on init. No such route existed,
so the editor's template bin was permanently empty and the 404 went unremarked
because the rejection was never handled.

The list is an allowlist rather than the module namespace, and the tests that
matter here are about that distinction rather than about the endpoint.
"""

import inspect

import pytest
from otto import templates as otto_templates

from alfred.core.routes.templates import (
    TEMPLATE_NAMES,
    available_templates,
)


class TestTheAllowlistMatchesTheEngine:
    def test_every_advertised_template_exists(self):
        """The endpoint skips missing names; this is what makes that safe.

        `available_templates` drops a name the installed engine does not
        provide, so one template disappearing degrades the bin rather than
        breaking the request. That is the right runtime behaviour and the
        wrong thing to be quiet about, since the symptom -- a template simply
        not offered -- looks like a product decision.
        """
        missing = [n for n in TEMPLATE_NAMES if not hasattr(otto_templates, n)]
        assert not missing, (
            f'advertised templates absent from the installed otto: {missing}. '
            'Either the engine dropped them or the allowlist has a typo; the '
            'endpoint would quietly stop offering them either way.'
        )

    def test_every_advertised_template_is_callable(self):
        not_callable = [
            n for n in TEMPLATE_NAMES if not callable(getattr(otto_templates, n, None))
        ]
        assert not not_callable, f'advertised but not callable: {not_callable}'

    def test_the_allowlist_has_no_duplicates(self):
        assert len(TEMPLATE_NAMES) == len(set(TEMPLATE_NAMES))


class TestTheAllowlistIsNarrowerThanTheNamespace:
    """This is the point of the file.

    `generateEdl` resolves a template with `getattr(templates, clip.name)`,
    where `clip.name` arrives from the client. The module namespace carries
    fourteen callables and only six are templates -- the rest are imports it
    happens to hold. Publishing or validating against the namespace would
    treat `ColorClip` and `concatenate_videoclips` as templates.
    """

    def test_the_namespace_holds_more_callables_than_are_advertised(self):
        namespace = {
            n
            for n in dir(otto_templates)
            if not n.startswith('_') and callable(getattr(otto_templates, n))
        }
        assert namespace - set(TEMPLATE_NAMES), (
            'the namespace no longer holds anything beyond the allowlist, so '
            'this test has stopped being evidence of anything -- check '
            'whether otto.templates changed and simplify accordingly'
        )

    @pytest.mark.parametrize(
        'leaked',
        ['ColorClip', 'TextClip', 'CompositeVideoClip', 'concatenate_videoclips'],
    )
    def test_imported_helpers_are_not_advertised_as_templates(self, leaked):
        """Named individually so a regression says which one came back."""
        assert hasattr(
            otto_templates, leaked
        ), f'{leaked} is no longer in otto.templates, so this guard is stale'
        assert leaked not in TEMPLATE_NAMES
        assert leaked not in [t.name for t in available_templates()]

    def test_nothing_advertised_comes_from_moviepy(self):
        for name in TEMPLATE_NAMES:
            fn = getattr(otto_templates, name, None)
            module = getattr(fn, '__module__', '')
            assert not module.startswith('moviepy'), (
                f'{name} resolves to {module}, which is a moviepy primitive '
                'rather than one of this project\'s templates'
            )


class TestTheDescription:
    def test_engine_supplied_parameters_are_not_offered_to_callers(self):
        """`clipsize` and `duration` come from the render, not the form.

        The bin builds fields from this list, so anything the engine fills in
        itself would show up as a field the user is invited to set and which
        is then ignored.
        """
        for template in available_templates():
            assert 'clipsize' not in template.parameters
            assert 'duration' not in template.parameters
            assert 'data' not in template.parameters

    def test_deprecated_templates_are_flagged(self):
        """otto spells it DEPRICATED; three templates carry it today."""
        flagged = {t.name for t in available_templates() if t.deprecated}
        assert flagged, (
            'nothing is flagged deprecated any more -- if otto fixed the '
            'spelling, the detection in _describe needs checking, because it '
            'matches the misspelling deliberately'
        )
        for name in flagged:
            doc = inspect.getdoc(getattr(otto_templates, name)) or ''
            assert 'DEPRICATED' in doc.upper() or 'DEPRECATED' in doc.upper()

    def test_current_templates_are_not_flagged_deprecated(self):
        current = {t.name for t in available_templates() if not t.deprecated}
        assert 'title' in current
        assert 'textBox' in current

    def test_every_template_reports_at_least_one_caller_parameter(self):
        for template in available_templates():
            assert template.parameters, (
                f'{template.name} advertises no parameters, so the bin would '
                'render it as a field-less template'
            )
