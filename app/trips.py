"""Trip workflow: projected dates email -> firm dates email with confirm link -> confirmed list."""
from datetime import datetime

from flask import url_for

from .emailer import send_batch
from .extensions import db
from .models import Customer, Stop

PROJECTED_SUBJECT = 'Heads up: {area} around {dates}'
PROJECTED_BODY = (
    "Hi {name},\n\n"
    "We're planning to be in the {area} area around {dates}. These dates aren't final yet. "
    "We'll email you again with firm dates and a link to confirm your spot.\n\n"
    "— Kelsey")

FIRM_SUBJECT = "We'll be in {area} {dates} — confirm your spot"
FIRM_BODY = (
    "Hi {name},\n\n"
    "We'll be in the {area} area {dates}! Tap the link below to confirm you'd like a visit:\n\n"
    "{link}\n\n"
    "— Kelsey")


def sync_stops(trip):
    """Put everyone currently in the trip's area on the trip (picks up new sign-ups)."""
    on_trip = {s.customer_id for s in trip.stops}
    for c in Customer.query.filter_by(area=trip.area):
        if c.id not in on_trip:
            trip.stops.append(Stop(customer=c))
    db.session.commit()


def fill(text, stop):
    parts = (stop.customer.name or '').split()
    return (text
            .replace('{name}', parts[0] if parts else 'there')
            .replace('{area}', stop.trip.area)
            .replace('{dates}', stop.trip.dates)
            .replace('{link}', url_for('public.confirm', token=stop.token, _external=True)))


def send_step(trip, step, subject, body):
    """Email everyone on the trip who hasn't had this step yet. Returns (sent, failed)."""
    field = {'projected': 'projected_sent_at', 'firm': 'firm_sent_at'}[step]
    if step == 'firm' and '{link}' not in body:
        body += '\n\nConfirm your spot: {link}'

    sync_stops(trip)
    pending = [s for s in trip.stops
               if s.customer.email and getattr(s, field) is None
               and not s.confirmed_at and not s.declined_at]
    sent_to = send_batch([(s.customer.email, fill(subject, s), fill(body, s)) for s in pending])

    now = datetime.now()
    for s in pending:
        if s.customer.email in sent_to:
            setattr(s, field, now)
    db.session.commit()
    sent = sum(1 for s in pending if s.customer.email in sent_to)
    return sent, len(pending) - sent


def stop_status(stop):
    if stop.confirmed_at:
        return 'Confirmed'
    if stop.declined_at:
        return "Can't make it"
    if not stop.customer.email:
        return 'No email — call/text'
    if stop.firm_sent_at:
        return 'Waiting to hear back'
    if stop.projected_sent_at:
        return 'Got projected dates'
    return 'Not emailed yet'
