"""Shared fixtures. Tests run against a real MySQL 8.0.46 (see CLAUDE.md), using the database `faceid_test`."""

import re
import runpy
from pathlib import Path

import pytest

from faceid import create_app, passwords
from faceid.store import db

passwords.ROUNDS = 4  # the minimum bcrypt allows; production keeps 12

INSTANCE_CONFIG = Path(__file__).parent.parent / "instance" / "config.py"


@pytest.fixture(scope="session")
def test_config():
    local = runpy.run_path(str(INSTANCE_CONFIG))
    config = {key: value for key, value in local.items() if key.isupper()}
    config.update(DB_NAME="faceid_test", TESTING=True)
    return config


@pytest.fixture
def empty_app(test_config):
    """An app whose database does not exist yet."""
    db.drop_database(test_config)
    return create_app(test_config)


@pytest.fixture
def cli(empty_app):
    return empty_app.test_cli_runner()


@pytest.fixture
def app(test_config):
    """An app on a freshly upgraded, empty database."""
    db.drop_database(test_config)
    db.upgrade(test_config)
    return create_app(test_config)


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client, url):
    html = client.get(url).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, f"no CSRF token on {url}"
    return match.group(1)


def submit(client, url, data, follow_redirects=True):
    """Fill in and post the form on `url`, the way a browser would."""
    return client.post(url, data={**data, "csrf_token": csrf_token(client, url)}, follow_redirects=follow_redirects)


def login(client, identifier, password):
    return submit(client, "/login", {"identifier": identifier, "password": password})


def create_admin(app, email="admin@college.test", password="admin-pass-1"):
    result = app.test_cli_runner().invoke(
        args=["create-admin"], input=f"admin\n{email}\n{password}\n{password}\n"
    )
    assert result.exit_code == 0, result.output
    return email, password


@pytest.fixture
def admin_client(app, client):
    email, password = create_admin(app)
    login(client, email, password)
    return client
