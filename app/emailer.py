from flask import current_app
from flask_mail import Message

from .extensions import mail


def send_batch(messages):
    """Send (to, subject, body) tuples over one SMTP connection.

    Returns the set of addresses that went out. One bad address doesn't stop the rest;
    if Gmail drops the connection, everything after that counts as not sent.
    """
    sent = set()
    try:
        with mail.connect() as conn:
            for to, subject, body in messages:
                try:
                    conn.send(Message(subject, recipients=[to], body=body))
                    sent.add(to)
                except Exception:
                    current_app.logger.exception('Email to %s failed', to)
    except Exception:
        current_app.logger.exception('Email batch aborted')
    return sent
