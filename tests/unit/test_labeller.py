"""The labeller adapter (`alfred/core/utils/labeller.py`), against a stand-in
for the chat route: what is asked, what is read out of the answer, and how
each failure is said.
"""

import json

import httpx
import pytest

from alfred import config
from alfred.core.utils import labeller
from alfred.core.utils.labeller import Labeller, category_from, score_from, status

ROUTE = 'http://labels.test:11434/v1'
MODEL = 'small-model'


@pytest.fixture
def route(monkeypatch):
    monkeypatch.setattr(config, 'LABELLER_URL', ROUTE)
    monkeypatch.setattr(config, 'LABELLER_MODEL', MODEL)
    monkeypatch.setattr(config, 'LABELLER_TIMEOUT', 5)


def completion(content):
    return {'choices': [{'message': {'role': 'assistant', 'content': content}}]}


def recording(content):
    """A transport answering `content` as a chat completion, keeping each
    request as `(method, url, body)`."""
    sent = []

    def handler(request):
        sent.append((request.method, str(request.url), json.loads(request.content)))
        return httpx.Response(200, json=completion(content))

    return httpx.MockTransport(handler), sent


def refusing(exc):
    def handler(request):
        raise exc

    return httpx.MockTransport(handler)


def answering(status_code, **kwargs):
    return httpx.MockTransport(lambda request: httpx.Response(status_code, **kwargs))


class TestWhatIsAsked:
    def test_a_category_is_one_chat_request_naming_the_model_and_the_categories(
        self, route
    ):
        transport, sent = recording('Story.')
        found = Labeller(transport).category(
            'Oh no, the tower fell!', ['rules', 'story']
        )
        assert found == 'story'
        [(method, url, body)] = sent
        assert (method, url) == ('POST', f'{ROUTE}/chat/completions')
        assert body['model'] == MODEL
        assert body['max_tokens'] == labeller.ANSWER_TOKENS
        assert body['temperature'] == 0
        [message] = body['messages']
        assert message['role'] == 'user'
        assert 'rules, story' in message['content']
        assert message['content'].endswith('Oh no, the tower fell!')

    def test_a_score_is_asked_as_a_whole_number_and_read_as_a_share(self, route):
        transport, sent = recording('I would say 7.')
        assert Labeller(transport).alone('Welcome to the show.') == 0.7
        [(_, _, body)] = sent
        assert f'0 to {labeller.SCALE}' in body['messages'][0]['content']

    def test_the_text_sent_is_cut_to_length(self, route):
        transport, sent = recording('rules')
        Labeller(transport).category('x' * (labeller.LABEL_CHARS + 500), ['rules'])
        assert sent[0][2]['messages'][0]['content'].count('x') == labeller.LABEL_CHARS

    def test_no_categories_asks_nothing(self, route):
        transport, sent = recording('rules')
        assert Labeller(transport).category('said', []) == ''
        assert sent == []


class TestWhatIsRead:
    def test_the_longest_category_named_wins_whatever_the_case(self):
        assert category_from('Game Rules, clearly.', ['game', 'game rules']) == (
            'game rules'
        )

    def test_an_answer_naming_none_is_empty(self):
        assert category_from('Neither.', ['a', 'b']) == ''

    def test_a_score_is_the_first_number_held_to_the_range(self):
        assert score_from('8') == 0.8
        assert score_from('Score: 10/10') == 1.0
        assert score_from('12') == 1.0
        assert score_from('about 3.5, maybe 9') == 0.35

    def test_no_number_is_no_score(self):
        assert score_from('hard to say') is None


class TestFailures:
    def test_none_configured(self, monkeypatch):
        monkeypatch.setattr(config, 'LABELLER_URL', None)
        with pytest.raises(labeller.NoLabeller, match='ALFRED_LABELLER_URL'):
            Labeller().alone('said')
        assert status().configured is False

    def test_no_model_is_no_labeller(self, route, monkeypatch):
        monkeypatch.setattr(config, 'LABELLER_MODEL', None)
        assert 'ALFRED_LABELLER_MODEL' in labeller.problem()
        found = status()
        assert (found.configured, found.ok) == (True, False)
        assert 'ALFRED_LABELLER_MODEL' in found.detail

    def test_a_bad_address(self, monkeypatch):
        monkeypatch.setattr(config, 'LABELLER_URL', 'labels.test')
        assert 'http(s)' in labeller.problem()

    def test_one_that_cannot_be_reached_names_itself(self, route):
        with pytest.raises(labeller.LabellerFailed) as failed:
            Labeller(refusing(httpx.ConnectError('refused'))).alone('said')
        assert str(failed.value).startswith(f'the labeller at {ROUTE}:')
        assert 'refused' in str(failed.value)

    def test_an_error_status_is_a_failure_with_the_status(self, route):
        with pytest.raises(labeller.LabellerFailed, match='500'):
            Labeller(answering(500, text='broke')).alone('said')

    @pytest.mark.parametrize('text', ['<html>', '{"choices": []}', '{"data": 1}', '[]'])
    def test_an_answer_that_is_not_a_chat_completion(self, route, text):
        with pytest.raises(labeller.LabellerFailed, match='not a chat completion'):
            Labeller(answering(200, text=text)).alone('said')

    def test_a_long_reason_is_cut(self, route):
        with pytest.raises(labeller.LabellerFailed) as failed:
            Labeller(answering(500, text='x' * 1000)).alone('said')
        assert len(str(failed.value)) <= labeller.REASON_LIMIT


class TestStatus:
    def test_answering_and_serving_the_model(self, route):
        asked = []

        def handler(request):
            asked.append((request.method, str(request.url)))
            return httpx.Response(
                200, json={'object': 'list', 'data': [{'id': MODEL, 'object': 'model'}]}
            )

        found = status(transport=httpx.MockTransport(handler))
        assert found == labeller.LabellerStatus(True, True, None)
        assert asked == [('GET', f'{ROUTE}/models')]

    def test_a_route_that_does_not_serve_the_model_says_so(self, route):
        found = status(transport=answering(200, json={'data': [{'id': 'other'}]}))
        assert (found.configured, found.ok) == (True, False)
        assert MODEL in found.detail

    def test_a_list_of_another_shape_is_still_an_answer(self, route):
        assert status(transport=answering(200, json={'models': []})).ok is True
        assert status(transport=answering(200, text='[]')).ok is True

    def test_an_error_status_is_not_ok(self, route):
        found = status(transport=answering(503))
        assert (found.ok, '503' in found.detail) == (False, True)

    def test_not_answering_says_why(self, route):
        found = status(transport=refusing(httpx.ConnectError('refused')))
        assert (found.configured, found.ok) == (True, False)
        assert 'refused' in found.detail
