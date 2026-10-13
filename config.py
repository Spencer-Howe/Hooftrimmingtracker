import os
from dotenv import load_dotenv

load_dotenv(os.getenv('ENV_FILE', '.env'))


class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-only-change-me')
    BUSINESS_NAME = os.getenv('BUSINESS_NAME', 'Kelsey Trimming Services')

    # Relative sqlite paths resolve inside instance/ (mounted as a volume in Docker)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///kelsey.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Kelsey's Gmail over SMTP using an App Password
    # (Google Account > Security > 2-Step Verification > App passwords)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 465))
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', '1') == '1'
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', '0') == '1'
    MAIL_USERNAME = os.getenv('GMAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
    MAIL_DEFAULT_SENDER = (BUSINESS_NAME, os.getenv('GMAIL_USERNAME', 'noreply@example.com'))

    FLASK_ADMIN_SWATCH = 'flatly'
