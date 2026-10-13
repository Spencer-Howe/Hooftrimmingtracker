import click
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import db, login_manager, mail

# Starter areas; Kelsey edits these on the Areas page
DEFAULT_AREAS = [
    ('925', 'Riverside / Temecula'),
    ('920', 'North San Diego County'),
    ('923', 'San Bernardino'),
    ('935', 'High Desert'),
]


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Behind nginx/Cloudflare: trust X-Forwarded-Proto/Host so confirm links are https://
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))

    from .views import public
    app.register_blueprint(public)

    from .admin import setup_admin
    setup_admin(app)

    register_cli(app)
    return app


def register_cli(app):
    from .models import Area, User

    @app.cli.command('init-db')
    def init_db():
        """Create tables and seed starter areas. Safe to re-run."""
        db.create_all()
        if not Area.query.first():
            db.session.add_all(Area(zip_prefix=p, name=n) for p, n in DEFAULT_AREAS)
        db.session.commit()
        click.echo('Database ready.')

    @app.cli.command('create-user')
    @click.argument('username')
    @click.password_option()
    def create_user(username, password):
        """Create a login, or reset the password if the user exists."""
        user = User.query.filter_by(username=username).first() or User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'User {username} saved.')

    @app.cli.command('seed-demo')
    @click.option('--count', default=50, show_default=True)
    def seed_demo_cmd(count):
        """Load fake Central/SoCal customers for demos (replaces earlier demo rows, sends no email)."""
        from .demo import seed_demo
        added, replaced = seed_demo(count)
        click.echo(f'Added {added} demo customers (replaced {replaced}).')
