from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'public.login'
