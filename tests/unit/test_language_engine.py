"""The language engine adapter (`alfred/core/utils/language_engine.py`),
against a stand-in for the engine's HTTP: what is sent, what is read, and
how each failure is said.
"""

import json

import httpx
import pytest

from alfred import config
from alfred.core.utils import language_engine
from alfred.core.utils.language_engine import (
    Line,
    Reading,
    read,
    status,
    transcript_text,
)

ANSWER = {
    'conversation_id': 1,
    'title': 'x',
    'total_duration': 30.0,
    'speakers': {
        'Alice': {'color': '#ff6b6b', 'index': 0, 'contributions': 2},
        'Bob': {'color': '#00d4ff', 'index': 1, 'contributions': 1},
    },
    'threads': [
        {
            'name': 'Rules',
            'color': '#00d4ff',
            'points': [
                {
                    'time': 0,
                    'intensity': 0.5,
                    'text': 'Alice: the rules',
                    'speaker': 'Alice',
                },
                {'time': 30, 'intensity': 0.2, 'text': 'Bob: rules?', 'speaker': 'Bob'},
            ],
            'total_intensity': 0.7,
        }
    ],
    'tangents': [
        {
            'start_time': 30,
            'end_time': 45,
            'tangent_type': 'resolved',
            'topics': ['Rules'],
            'start_text': 'Bob: but wait',
            'resolution_text': 'Alice: anyway, back to it',
        },
        {
            'start_time': 10,
            'end_time': 12,
            'tangent_type': 'orphaned',
            'topics': [],
            'start_text': 'Alice: however',
            'resolution_text': None,
        },
    ],
}

LINES = [
    Line(start=0, speaker='Alice', text='Here are the rules.'),
    Line(start=10.4, speaker=None, text='However.'),
    Line(start=30, speaker='Bob', text='But wait: rules?'),
]


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', 'http://words.test:8000')
    monkeypatch.setattr(config, 'LANGUAGE_ENGINE_TIMEOUT', 5)


def answering(handler):
    return httpx.MockTransport(handler)


class TestWhatIsSent:
    def test_each_line_with_its_time_and_speaker_or_nobody(self):
        assert transcript_text(LINES) == (
            '[0:00] Alice: Here are the rules.\n'
            '[0:10] Unknown: However.\n'
            '[0:30] Bob: But wait: rules?'
        )

    def test_a_speaker_s_colon_would_split_the_line_so_it_goes(self):
        text = transcript_text([Line(start=65, speaker='Me: myself', text='hi')])
        assert text == '[1:05] Me  myself: hi'

    def test_an_empty_line_is_left_out(self):
        assert transcript_text([Line(start=0, speaker='A', text='  ')]) == ''

    def test_the_request_is_the_text_and_a_title(self, engine):
        seen = []

        def handler(request):
            seen.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json=ANSWER)

        read(LINES, title='6b01', transport=answering(handler))
        [(path, body)] = seen
        assert path == '/api/conversations/analyze'
        assert body == {'text': transcript_text(LINES), 'title': '6b01'}


class TestWhatIsRead:
    def test_the_engine_s_id_for_the_conversation_is_kept(self, engine):
        """Mutation: drop the id -- red; the engine's page opens a reading by it."""
        kept = read(
            LINES, transport=answering(lambda r: httpx.Response(200, json=ANSWER))
        )
        assert kept.id == 1
        without = read(
            LINES,
            transport=answering(
                lambda r: httpx.Response(200, json={**ANSWER, 'conversation_id': 'x'})
            ),
        )
        assert without.id is None

    def test_speakers_topics_and_tangents_in_alfred_s_words(self, engine):
        found = read(
            LINES, transport=answering(lambda r: httpx.Response(200, json=ANSWER))
        )
        assert found.speakers == {
            'Alice': {'color': '#ff6b6b', 'contributions': 2},
            'Bob': {'color': '#00d4ff', 'contributions': 1},
        }
        assert found.topics == [
            {
                'name': 'Rules',
                'color': '#00d4ff',
                'points': [
                    {'time': 0, 'intensity': 0.5, 'speaker': 'Alice'},
                    {'time': 30, 'intensity': 0.2, 'speaker': 'Bob'},
                ],
            }
        ]
        # In order of time, whatever order the engine gave them.
        assert [t['start'] for t in found.tangents] == [10, 30]
        assert found.tangents[1] == {
            'start': 30,
            'end': 45,
            'type': 'resolved',
            'topics': ['Rules'],
            'text': 'Bob: but wait',
            'resolution': 'Alice: anyway, back to it',
        }

    def test_nothing_to_read_asks_nothing(self, engine):
        def handler(request):
            raise AssertionError('asked')

        assert read([], transport=answering(handler)) == Reading()

    def test_an_answer_that_leaves_things_out_is_empty_there(self, engine):
        found = read(LINES, transport=answering(lambda r: httpx.Response(200, json={})))
        assert (found.speakers, found.topics, found.tangents) == ({}, [], [])


class TestFailures:
    def test_none_configured(self, monkeypatch):
        monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', None)
        with pytest.raises(
            language_engine.NoLanguageEngine, match='ALFRED_LANGUAGE_ENGINE_URL'
        ):
            read(LINES)
        assert status().configured is False

    def test_a_bad_address(self, monkeypatch):
        monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', 'words.test')
        assert 'http(s)' in language_engine.problem()

    def test_an_engine_that_cannot_be_reached_names_itself(self, engine):
        def handler(request):
            raise httpx.ConnectError('refused')

        with pytest.raises(language_engine.LanguageEngineFailed) as failed:
            read(LINES, transport=answering(handler))
        assert str(failed.value).startswith(
            'the language engine at http://words.test:8000:'
        )

    def test_an_error_status_is_a_failure_with_the_status(self, engine):
        with pytest.raises(language_engine.LanguageEngineFailed, match='500'):
            read(
                LINES, transport=answering(lambda r: httpx.Response(500, text='broke'))
            )

    def test_an_answer_that_is_not_json(self, engine):
        with pytest.raises(language_engine.LanguageEngineFailed, match='not JSON'):
            read(
                LINES, transport=answering(lambda r: httpx.Response(200, text='<html>'))
            )

    def test_a_long_reason_is_cut(self, engine):
        with pytest.raises(language_engine.LanguageEngineFailed) as failed:
            read(
                LINES,
                transport=answering(lambda r: httpx.Response(500, text='x' * 1000)),
            )
        assert len(str(failed.value)) <= language_engine.REASON_LIMIT


class TestStatus:
    def test_answering(self, engine):
        found = status(
            transport=answering(lambda r: httpx.Response(200, json={'status': 'ok'}))
        )
        assert found == language_engine.EngineStatus(True, True, None)

    def test_not_answering_says_why(self, engine):
        def handler(request):
            raise httpx.ConnectError('refused')

        found = status(transport=answering(handler))
        assert (found.configured, found.ok) == (True, False)
        assert 'refused' in found.detail
