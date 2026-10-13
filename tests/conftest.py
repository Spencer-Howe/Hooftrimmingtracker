import pytest

from app import create_app
from app.extensions import db, mail
from app.models import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    MAIL_DEFAULT_SENDER = ('Kelsey Trimming Services', 'kelsey@example.com')
    SECRET_KEY = 'test'


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        app.test_cli_runner().invoke(args=['init-db'])
        user = User(username='kelsey')
        user.set_password('pw')
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in(client):
    client.post('/login', data={'username': 'kelsey', 'password': 'pw'})
    return client


@pytest.fixture
def outbox(app):
    with mail.record_messages() as sent:
        yield sent
