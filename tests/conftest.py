import pytest

from app import application as flask_app


@pytest.fixture
def application():
    yield flask_app


@pytest.fixture
def client(application):
    return application.test_client()