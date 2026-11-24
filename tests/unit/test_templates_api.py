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
    TEMPLATE_LABELS,
    TEMPLATE_NAMES,
    UNDRIVABLE_TEMPLATES,
    available_templates,
)


def unadvertised_callables():
    """Every callable in otto's namespace that is not an advertised template.

    Derived, not typed. The guard below used a hand-written list of four
    names -- `ColorClip`, `TextClip`, `CompositeVideoClip`,
    `concatenate_videoclips` -- against a namespace holding eight that must be
    refused, so five were unchecked and nothing said so. A list written once
    describes the namespace on the day it was written; this describes it on
    the day the test runs, and a new import in otto arrives as a new test
    case rather than as a silent gap.
    """
    allowed = set(TEMPLATE_NAMES) | set(UNDRIVABLE_TEMPLATES)
    return sorted(
        name
        for name in dir(otto_templates)
        if not name.startswith('_')
        and callable(getattr(otto_templates, name))
        and name not in allowed
    )


class TestTheAllowlistMatchesTheEngine:
    def test_every_advertised_template_is_in_the_engine_s_registry(self):
        """The endpoint skips missing names; this is what makes that safe.

        The registry, `otto.templates.TEMPLATES`, because it is what
        `generateEdl` looks a template clip's name up in: a name outside it is
        refused at render time, whatever else the module holds.

        `available_templates` drops a name the installed engine does not
        provide, so one template disappearing degrades the bin rather than
        breaking the request. That is the right runtime behaviour and the
        wrong thing to be quiet about, since the symptom -- a template simply
        not offered -- looks like a product decision.
        """
        missing = [n for n in TEMPLATE_NAMES if n not in otto_templates.TEMPLATES]
        assert not missing, (
            f'advertised templates absent from the installed otto: {missing}. '
            'Either the engine dropped them or the allowlist has a typo; the '
            'endpoint would quietly stop offering them either way.'
        )

    def test_every_advertised_template_is_callable(self):
        not_callable = [
            n for n in TEMPLATE_NAMES if not callable(otto_templates.TEMPLATES.get(n))
        ]
        assert not not_callable, f'advertised but not callable: {not_callable}'

    def test_every_template_the_engine_has_is_offered_or_left_out_on_purpose(self):
        """A template new to otto's registry should arrive here as a decision.

        Otherwise it would be one the bin silently never offers. Excluded
        names must be real templates too, or the exclusion is stale.
        """
        registry = set(otto_templates.TEMPLATES)
        undecided = registry - set(TEMPLATE_NAMES) - set(UNDRIVABLE_TEMPLATES)
        assert not undecided, (
            f'otto renders {sorted(undecided)}, which is neither offered '
            '(TEMPLATE_NAMES) nor deliberately left out (UNDRIVABLE_TEMPLATES)'
        )
        assert set(UNDRIVABLE_TEMPLATES) <= registry, (
            f'{sorted(set(UNDRIVABLE_TEMPLATES) - registry)} left out, '
            'but the engine has no such template any more'
        )

    def test_the_allowlist_has_no_duplicates(self):
        assert len(TEMPLATE_NAMES) == len(set(TEMPLATE_NAMES))


class TestTheAllowlistIsNarrowerThanTheNamespace:
    """The module holds far more callables than templates.

    `otto.templates` imports what its templates are built from -- `ColorClip`,
    `concatenate_videoclips`, `rgbToDec` and more -- so most of the callables
    in its namespace are not templates. `generateEdl` used to resolve a
    clip's name against that namespace, which made every one of them
    reachable from an EDL; it looks names up in otto's registry now. The
    allowlist is what this API publishes, and these keep anything that is
    merely importable off it.
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

    @pytest.mark.parametrize('leaked', unadvertised_callables())
    def test_imported_helpers_are_not_advertised_as_templates(self, leaked):
        """Every unadvertised callable, named individually.

        Parametrised over the derived set rather than a written one, so the
        count of cases tracks the namespace. A regression still says which
        name came back, which is why this is one case per name rather than a
        single assertion over the set.
        """
        assert leaked not in TEMPLATE_NAMES
        assert leaked not in [t.name for t in available_templates()]

    def test_the_derived_set_is_not_empty(self):
        """A parametrised test over an empty list passes by vacuum.

        If otto's namespace ever holds nothing beyond the allowlist, the guard
        above silently becomes zero test cases and keeps reporting success.
        This is the assertion that notices.
        """
        assert unadvertised_callables(), (
            'nothing in otto.templates is outside the allowlist, so the guard '
            'above now runs zero cases -- check what changed in otto rather '
            'than trusting the green'
        )

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

    def test_every_template_has_a_label_of_its_own(self):
        """The editor shows the label, not otto's identifier.

        A name missing from TEMPLATE_LABELS falls back to the identifier,
        which is the leak the labels exist to stop; two templates sharing a
        label could not be told apart in the bin.

        Mutation: drop `textBox` from TEMPLATE_LABELS and this fails.
        """
        templates = available_templates()
        assert set(TEMPLATE_NAMES) <= set(TEMPLATE_LABELS)
        labels = [t.label for t in templates]
        assert all(t.label != t.name for t in templates), labels
        assert len(set(labels)) == len(labels), labels

    def test_every_template_has_a_description(self):
        """A template button's title is its description; otto gives
        `makeColor` none, so the server supplies one."""
        for template in available_templates():
            assert template.description, template.name
