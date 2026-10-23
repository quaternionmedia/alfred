"""Who may create an account, asked of the running app.

`POST /auth/register` was mounted unconditionally: anyone who could reach a
production server could give themselves an account on it. It is now governed
by ALFRED_ALLOW_REGISTRATION -- open by default in development, closed by
default under ALFRED_PRODUCTION, and an explicit value wins either way.

The parsing is unit-tested in `unit/test_registration_setting.py`. These
assert the route obeys whatever the setting resolves to, so each test resolves
it from an environment rather than poking a bare boolean in: the thing under
test is "this environment produces this behaviour".
"""

import pytest

from alfred import config
from alfred.config import resolve_allow_registration

pytestmark = pytest.mark.needs_db

DEVELOPMENT = {}
PRODUCTION = {'ALFRED_PRODUCTION': 'true'}


@pytest.fixture
def environment(monkeypatch):
    """Resolve registration from an environment, as the app does at boot."""

    def apply(env):
        monkeypatch.setattr(
            config, 'ALLOW_REGISTRATION', resolve_allow_registration(env)
        )

    return apply


@pytest.fixture
def register(api, fresh_email, password):
    def post(email=None, **extra):
        body = {
            'email': email or fresh_email('register'),
            'password': password,
            'first_name': 'Registrant',
        }
        body.update(extra)
        return api.post('/auth/register', json=body)

    return post


class TestDevelopmentIsOpen:
    def test_anyone_can_register(self, environment, register):
        environment(DEVELOPMENT)
        res = register()
        assert res.status_code == 201, res.text

    def test_the_new_account_can_log_in(
        self, environment, register, fresh_email, log_in
    ):
        environment(DEVELOPMENT)
        email = fresh_email('newcomer')
        assert register(email).status_code == 201

        assert log_in(email)

    def test_a_new_account_is_never_a_superuser(
        self, environment, register, fresh_email, users
    ):
        """Open registration must not be a way to the admin surface.

        fastapi-users drops `is_superuser` from a registration body (it
        creates with `safe=True`). Pinned because superusers now see every
        project, which raises the stakes of that one flag.
        """
        environment(DEVELOPMENT)
        email = fresh_email('climber')
        res = register(email, is_superuser=True, is_verified=True)
        assert res.status_code == 201, res.text
        assert users.find_one({'email': email})['is_superuser'] is False


class TestProductionIsClosed:
    def test_registration_is_refused_with_403(self, environment, register):
        environment(PRODUCTION)
        assert register().status_code == 403

    def test_the_refusal_says_registration_is_closed(self, environment, register):
        """A reason a person can act on, not a bare status.

        The SPA shows this text as it stands, so it has to make sense to
        someone who only wanted an account.
        """
        environment(PRODUCTION)
        detail = register().json()['detail']
        assert 'closed' in detail.lower()
        assert 'administrator' in detail.lower()

    def test_nothing_is_created(self, environment, register, fresh_email, users):
        environment(PRODUCTION)
        email = fresh_email('refused')
        register(email)
        assert users.find_one({'email': email}) is None

    def test_a_closed_server_does_not_explain_the_body_it_wants(self, api, environment):
        """403 before validation, not a 422 describing a valid registration.

        The closed check is a dependency, and dependencies resolve before the
        body is validated -- so an empty body gets the same refusal as a
        well-formed one.
        """
        environment(PRODUCTION)
        assert api.post('/auth/register', json={}).status_code == 403

    def test_existing_accounts_can_still_log_in(
        self, environment, make_account, log_in
    ):
        """Closing registration closes registration, and nothing else."""
        account = make_account('existing')
        environment(PRODUCTION)
        assert log_in(account.email)


class TestAnExplicitSettingWins:
    @pytest.mark.parametrize('value', ['true', '1', 'yes', 'on'])
    def test_it_can_open_production(self, environment, register, value):
        environment({**PRODUCTION, 'ALFRED_ALLOW_REGISTRATION': value})
        assert register().status_code == 201

    @pytest.mark.parametrize('value', ['false', '0', 'no', 'off', 'closed'])
    def test_it_can_close_development(self, environment, register, value):
        environment({'ALFRED_ALLOW_REGISTRATION': value})
        assert register().status_code == 403


class TestTheDevAccountsAddressIsReserved:
    """The auth bypass acts as ALFRED_DEV_USER_EMAIL, which owns the dev seeds.

    The bypass creates that account on first use, so on a stack where it had
    never run -- registration open, bypass off -- the address was free, and
    whoever registered it owned the seeded projects.
    """

    def test_registering_it_is_refused_with_a_reason(self, environment, register):
        environment(DEVELOPMENT)

        res = register(config.DEV_USER_EMAIL)

        assert res.status_code == 400, res.text
        assert 'development login' in res.json()['detail']

    def test_in_any_case(self, environment, register):
        environment(DEVELOPMENT)
        assert register(config.DEV_USER_EMAIL.upper()).status_code == 400

    def test_nothing_is_created(self, environment, register, users):
        """Counted rather than looked for: a test here may have made the dev
        account itself, as the bypass would."""
        environment(DEVELOPMENT)
        before = users.count_documents({'email': config.DEV_USER_EMAIL})
        register(config.DEV_USER_EMAIL)
        assert users.count_documents({'email': config.DEV_USER_EMAIL}) == before


@pytest.fixture
def dev_account(users):
    """The account the bypass creates, as it creates it -- here without the bypass."""
    users.update_one(
        {'email': config.DEV_USER_EMAIL},
        {
            '$setOnInsert': {
                'email': config.DEV_USER_EMAIL,
                'first_name': 'Dev',
                'hashed_password': '!dev-no-login',
                'is_active': True,
                'is_verified': True,
                'is_superuser': True,
            }
        },
        upsert=True,
    )
    return users.find_one({'email': config.DEV_USER_EMAIL})


def dev_login(api, password):
    return api.post(
        '/auth/jwt/login',
        data={'username': config.DEV_USER_EMAIL, 'password': password},
    )


class TestTheDevAccountCannotBeLoggedInto:
    """It stores no usable password, and nothing may give it one."""

    def test_a_login_is_refused_like_a_wrong_password(self, api, dev_account):
        """It was a 500: passlib cannot identify `!dev-no-login` as a hash."""
        res = dev_login(api, 'any password at all')
        assert res.status_code == 400, res.text
        assert res.json()['detail'] == 'LOGIN_BAD_CREDENTIALS'

    def test_a_superuser_cannot_set_its_password(self, api, make_account, dev_account):
        root = make_account('root', superuser=True)

        res = api.patch(
            f'/users/{dev_account["_id"]}',
            json={'password': 'a password somebody chose'},
            headers=root.headers,
        )

        assert res.status_code == 400, res.text
        assert 'no password' in res.json()['detail']['reason']
        assert dev_login(api, 'a password somebody chose').status_code == 400

    def test_no_reset_token_is_issued_for_it(self, api, dev_account, monkeypatch):
        from alfred.core.routes.users import UserManager

        issued = []

        async def record(self, user, token, request=None):
            issued.append(token)

        monkeypatch.setattr(UserManager, 'on_after_forgot_password', record)

        res = api.post('/auth/forgot-password', json={'email': config.DEV_USER_EMAIL})

        assert res.status_code == 202, 'the same answer as for any address'
        assert issued == []
