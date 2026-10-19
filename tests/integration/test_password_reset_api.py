"""A forgotten password can be reset, from the request to the new login.

The routes existed -- fastapi-users' forgot-password and reset-password -- but
the token they turn on was only ever printed to the server's log, so outside
development nobody could finish a reset. With mail configured it is mailed as
a link to the app's account page. These follow one through the running app,
taking the token from the link in the mail as a person would.

Mail is configured here and delivered nowhere: the message is kept, not sent.
"""

import re
from urllib.parse import unquote

import pytest

from alfred import config
from alfred.core.utils import account_mail

pytestmark = pytest.mark.needs_db

NEW_PASSWORD = 'a new and longer password'


@pytest.fixture
def mailbox(monkeypatch):
    """Mail configured, and every message kept here instead of sent."""
    monkeypatch.setattr(config, 'EMAIL_SERVER', 'smtp.example.com')
    monkeypatch.setattr(config, 'EMAIL_USERNAME', 'alfred@example.com')
    monkeypatch.setattr(config, 'PUBLIC_URL', 'https://alfred.example.com')
    kept = []

    def keep(to, subject, message, attachments=None, timeout=None):
        kept.append(dict(to=to, subject=subject, body=message))
        return True

    monkeypatch.setattr(account_mail, 'sendMail', keep)
    monkeypatch.setattr(account_mail, 'dispatch', lambda send: send())
    return kept


def link_in(mail):
    return re.search(r'https://\S+', mail['body']).group(0)


def token_from(link):
    return unquote(re.search(r'token=([^&\s]+)', link).group(1))


def forgot(api, email):
    res = api.post('/auth/forgot-password', json={'email': email})
    assert res.status_code == 202, res.text


def reset(api, token, password=NEW_PASSWORD):
    return api.post('/auth/reset-password', json={'token': token, 'password': password})


def login(api, email, password):
    return api.post('/auth/jwt/login', data={'username': email, 'password': password})


class TestResettingAPassword:
    def test_the_whole_way_round(self, api, make_account, mailbox, password):
        alice = make_account('alice')

        forgot(api, alice.email)
        [mail] = mailbox
        assert mail['to'] == alice.email
        link = link_in(mail)
        assert link.startswith('https://alfred.example.com/#!/account/reset?token=')

        res = reset(api, token_from(link))

        assert res.status_code == 200, res.text
        assert login(api, alice.email, NEW_PASSWORD).status_code == 200
        assert login(api, alice.email, password).status_code == 400

    def test_a_link_works_once(self, api, make_account, mailbox):
        """The token carries a fingerprint of the old password hash."""
        alice = make_account('alice')
        forgot(api, alice.email)
        token = token_from(link_in(mailbox[0]))

        assert reset(api, token).status_code == 200
        again = reset(api, token, password='yet another password')

        assert again.status_code == 400
        assert again.json()['detail'] == 'RESET_PASSWORD_BAD_TOKEN'

    def test_a_made_up_token_is_refused(self, api):
        res = reset(api, 'not-a-token')
        assert res.status_code == 400
        assert res.json()['detail'] == 'RESET_PASSWORD_BAD_TOKEN'

    def test_an_address_with_no_account_gets_the_same_answer_and_no_mail(
        self, api, mailbox, fresh_email
    ):
        forgot(api, fresh_email('nobody'))
        assert mailbox == []

    def test_production_logs_the_request_but_not_the_token(
        self, api, make_account, mailbox, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        alice = make_account('alice')
        capsys.readouterr()

        forgot(api, alice.email)

        token = token_from(link_in(mailbox[0]))
        out = capsys.readouterr().out
        assert 'Password reset requested' in out
        assert token not in out

    def test_development_does_not_log_a_token_it_mailed(
        self, api, make_account, mailbox, monkeypatch, capsys
    ):
        """The log is where a development stack without mail finishes a reset;
        with mail, it has no reason to hold the credential."""
        monkeypatch.setattr(config, 'PRODUCTION', None)
        alice = make_account('alice')
        capsys.readouterr()

        forgot(api, alice.email)

        token = token_from(link_in(mailbox[0]))
        out = capsys.readouterr().out
        assert 'Password reset requested' in out
        assert token not in out


class TestWithoutMail:
    def test_nothing_is_sent_and_development_logs_the_token(
        self, api, make_account, monkeypatch, capsys
    ):
        """How a development stack, which rarely has mail, finishes a reset."""
        monkeypatch.setattr(config, 'PUBLIC_URL', None)
        monkeypatch.setattr(config, 'PRODUCTION', None)
        sent = []
        monkeypatch.setattr(account_mail, 'dispatch', sent.append)
        alice = make_account('alice')
        capsys.readouterr()

        forgot(api, alice.email)

        assert sent == []
        token = re.search(r'Token: (\S+)', capsys.readouterr().out).group(1)
        assert reset(api, token).status_code == 200
        assert login(api, alice.email, NEW_PASSWORD).status_code == 200


class TestConfirmingAnAddress:
    def test_the_whole_way_round(self, api, make_account, mailbox, users):
        alice = make_account('alice')
        users.update_one({'email': alice.email}, {'$set': {'is_verified': False}})

        res = api.post('/auth/request-verify-token', json={'email': alice.email})
        assert res.status_code == 202, res.text
        link = link_in(mailbox[0])
        assert '/#!/account/verify?token=' in link

        res = api.post('/auth/verify', json={'token': token_from(link)})

        assert res.status_code == 200, res.text
        assert users.find_one({'email': alice.email})['is_verified'] is True

    def test_the_answer_is_the_account(self, api, make_account, mailbox, users):
        """It was a 500 after every confirmation that worked: the route
        answered with the stored document, whose id serialises as `_id`."""
        alice = make_account('alice')
        users.update_one({'email': alice.email}, {'$set': {'is_verified': False}})
        api.post('/auth/request-verify-token', json={'email': alice.email})

        res = api.post('/auth/verify', json={'token': token_from(link_in(mailbox[0]))})

        assert res.status_code == 200, res.text
        assert res.json()['email'] == alice.email
        assert res.json()['is_verified'] is True
        assert len(res.json()['id']) == 24
