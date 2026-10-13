import re

from app.extensions import db
from app.models import Area, Customer, Stop, Trip

SIGNUP = {
    'name': 'Spencer Howe', 'email': 'Spencer@Example.com', 'phone': '555-1234',
    'zip_code': '92595', 'animals': ['Alpaca'], 'notes': '2 alpacas, shearing',
}


def add_customer(name='Amy Smith', email='amy@example.com', zip_code='92595',
                 area='Riverside / Temecula', **kw):
    c = Customer(name=name, email=email, zip_code=zip_code, area=area, **kw)
    db.session.add(c)
    db.session.commit()
    return c


def make_trip(client, area='Riverside / Temecula', dates='Oct 20–22'):
    resp = client.post('/admin/trip/new', data={'area': area, 'dates': dates})
    assert resp.status_code == 302
    return Trip.query.order_by(Trip.id.desc()).first()


def send(client, trip, step, subject='{area} {dates}', body='Hi {name} {link}'):
    return client.post(f'/admin/trip/{trip.id}/send/{step}', data={'subject': subject, 'body': body},
                       follow_redirects=True)


# --- sign-up ---------------------------------------------------------------

def test_signup_creates_customer_with_area_and_welcome(client, outbox):
    resp = client.post('/', data=SIGNUP)
    assert resp.status_code == 302 and resp.location.endswith('/thanks')
    c = Customer.query.one()
    assert (c.email, c.area, c.animals) == ('spencer@example.com', 'Riverside / Temecula', 'Alpaca')
    assert len(outbox) == 1 and 'Hi Spencer' in outbox[0].body


def test_repeat_signup_updates_instead_of_duplicating(client, outbox):
    client.post('/', data=SIGNUP)
    client.post('/', data={**SIGNUP, 'notes': 'now 3 alpacas'})
    c = Customer.query.one()
    assert '2 alpacas' in c.notes and 'now 3 alpacas' in c.notes
    assert len(outbox) == 1


def test_signup_validation_and_honeypot(client, outbox):
    resp = client.post('/', data={**SIGNUP, 'zip_code': 'abc'})
    assert resp.status_code == 200 and b'5-digit zip' in resp.data
    client.post('/', data={**SIGNUP, 'website': 'spam.biz'})
    assert Customer.query.count() == 0 and not outbox


def test_longest_zip_prefix_wins_and_unknown_is_unassigned(client):
    db.session.add(Area(zip_prefix='92562', name='Murrieta'))
    db.session.commit()
    client.post('/', data={**SIGNUP, 'zip_code': '92562'})
    client.post('/', data={**SIGNUP, 'email': 'b@example.com', 'zip_code': '59901'})
    assert {c.zip_code: c.area for c in Customer.query.all()} == {'92562': 'Murrieta', '59901': 'Unassigned'}


# --- admin basics ----------------------------------------------------------

def test_admin_requires_login(client):
    resp = client.get('/admin/')
    assert resp.status_code == 302 and '/login' in resp.location
    assert client.post('/login', data={'username': 'kelsey', 'password': 'nope'}).status_code == 200


def test_admin_pages_render(logged_in):
    add_customer()
    trip = make_trip(logged_in)
    for url in ['/admin/', f'/admin/trip/{trip.id}', '/admin/customer/', '/admin/area/', '/admin/customer/new/']:
        assert logged_in.get(url).status_code == 200, url


def test_editing_areas_regroups_customers(logged_in):
    c = add_customer(zip_code='92562')
    logged_in.post('/admin/area/new/', data={'zip_prefix': '92562', 'name': 'Murrieta'})
    assert db.session.get(Customer, c.id).area == 'Murrieta'


# --- trip flow -------------------------------------------------------------

def test_trip_includes_only_that_area(logged_in):
    add_customer('Amy Smith', 'amy@example.com')
    add_customer('Bob Jones', 'bob@example.com', zip_code='93706', area='Fresno')
    trip = make_trip(logged_in)
    assert [s.customer.name for s in trip.stops] == ['Amy Smith']


def test_projected_email_marks_notified_and_skips_no_email(logged_in, outbox):
    add_customer('Amy Smith', 'amy@example.com')
    add_customer('Bob Jones', None, phone='555-0000')
    trip = make_trip(logged_in)
    resp = send(logged_in, trip, 'projected', 'Heads up: {area} around {dates}', 'Hi {name}, {dates}')

    assert b'Sent 1 emails' in resp.data and b'No email' in resp.data
    assert len(outbox) == 1
    assert outbox[0].subject == 'Heads up: Riverside / Temecula around Oct 20–22'
    assert outbox[0].body == 'Hi Amy, Oct 20–22'
    amy = Stop.query.join(Customer).filter(Customer.name == 'Amy Smith').one()
    assert amy.projected_sent_at is not None


def test_resending_only_emails_new_people(logged_in, outbox):
    add_customer('Amy Smith', 'amy@example.com')
    trip = make_trip(logged_in)
    send(logged_in, trip, 'projected')
    add_customer('New Person', 'new@example.com')  # signed up after the first send
    send(logged_in, trip, 'projected')
    assert [m.recipients for m in outbox] == [['amy@example.com'], ['new@example.com']]


def test_firm_email_link_confirms_customer(logged_in, client, outbox):
    add_customer('Amy Smith', 'amy@example.com', animals='Alpaca')
    trip = make_trip(logged_in)
    send(logged_in, trip, 'firm', body='Hi {name}, confirm here: {link}')

    link = re.search(r'http://localhost(/confirm/\S+)', outbox[0].body).group(1)
    page = client.get(link)
    assert page.status_code == 200 and b'Riverside / Temecula' in page.data and b'Oct 20' in page.data

    resp = client.post(link, data={'answer': 'yes', 'name': 'Amy Smith', 'phone': '555-9999',
                                   'animals': ['Alpaca', 'Goat'], 'visit_notes': '3 alpacas, 1 goat hooves'})
    assert b"You're confirmed" in resp.data
    stop = Stop.query.one()
    assert stop.confirmed_at and stop.visit_notes == '3 alpacas, 1 goat hooves'
    assert stop.customer.phone == '555-9999' and stop.customer.animals == 'Alpaca, Goat'

    trip_page = logged_in.get(f'/admin/trip/{trip.id}')
    assert b'Confirmed (1)' in trip_page.data and b'1 goat hooves' in trip_page.data


def test_firm_email_adds_link_if_missing(logged_in, outbox):
    add_customer()
    send(logged_in, make_trip(logged_in), 'firm', body='We will be there {dates}')
    assert '/confirm/' in outbox[0].body


def test_cant_make_it_and_confirmed_people_skip_later_sends(logged_in, client, outbox):
    add_customer('Amy Smith', 'amy@example.com')
    add_customer('Bob Jones', 'bob@example.com')
    trip = make_trip(logged_in)
    amy, bob = sorted(trip.stops, key=lambda s: s.customer.name)
    client.post(f'/confirm/{amy.token}', data={'answer': 'no'})
    logged_in.post(f'/admin/stop/{bob.id}/yes')  # Bob confirmed by text
    send(logged_in, trip, 'firm')
    assert not outbox
    assert db.session.get(Stop, amy.id).declined_at and db.session.get(Stop, bob.id).confirmed_at


def test_bad_confirm_token_404s(client):
    assert client.get('/confirm/nope').status_code == 404


def test_trips_are_history(logged_in):
    add_customer()
    make_trip(logged_in, dates='Mar 3–5')
    make_trip(logged_in, dates='Oct 20–22')
    page = logged_in.get('/admin/').data
    assert b'Mar 3' in page and b'Oct 20' in page


def test_customer_export_csv(logged_in):
    add_customer('Amy Smith', 'amy@example.com')
    resp = logged_in.get('/admin/customer/export/csv/')
    assert resp.status_code == 200 and b'Amy Smith' in resp.data
