from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from .emailer import send_batch
from .extensions import db
from .models import ANIMALS, Customer, Stop, User, area_for_zip, clean_zip

public = Blueprint('public', __name__)

WELCOME_SUBJECT = "You're on the list!"
WELCOME_BODY = ("Hi {name},\n\nThanks for signing up! We'll email you when we're planning a trip "
                "to your area.\n\n— Kelsey")


def _business():
    return current_app.config['BUSINESS_NAME']


@public.route('/', methods=['GET', 'POST'])
def signup():
    form = request.form
    errors = []

    if request.method == 'POST':
        # Honeypot: real people never see or fill this field
        if form.get('website'):
            return redirect(url_for('public.thanks'))

        name = form.get('name', '').strip()
        email = form.get('email', '').strip().lower()
        zip_code = clean_zip(form.get('zip_code'))
        if not name:
            errors.append('Please enter your name.')
        if '@' not in email:
            errors.append('Please enter a valid email so we can send you dates.')
        if not zip_code:
            errors.append('Please enter a 5-digit zip code.')

        if not errors:
            customer = Customer.query.filter_by(email=email).first()
            is_new = customer is None
            if is_new:
                customer = Customer(email=email)
                db.session.add(customer)
            notes = form.get('notes', '').strip()
            if notes and customer.notes:
                notes = f'{customer.notes}\n---\n{notes}'

            customer.name = name
            customer.phone = form.get('phone', '').strip() or customer.phone
            customer.zip_code = zip_code
            customer.area = area_for_zip(zip_code)
            customer.animals = ', '.join(form.getlist('animals')) or customer.animals
            customer.notes = notes or customer.notes
            db.session.commit()

            if is_new:
                first = name.split()[0]
                send_batch([(email, WELCOME_SUBJECT, WELCOME_BODY.replace('{name}', first))])
            return redirect(url_for('public.thanks'))

    return render_template('signup.html', form=form, errors=errors, animals=ANIMALS, business=_business())


@public.route('/thanks')
def thanks():
    return render_template('thanks.html', business=_business())


@public.route('/confirm/<token>', methods=['GET', 'POST'])
def confirm(token):
    """Personal link from the firm-dates email. Looks like the sign-up page, pre-filled."""
    stop = Stop.query.filter_by(token=token).first() or abort(404)
    customer = stop.customer

    if request.method == 'POST':
        customer.name = request.form.get('name', '').strip() or customer.name
        customer.phone = request.form.get('phone', '').strip() or customer.phone
        customer.animals = ', '.join(request.form.getlist('animals')) or customer.animals
        stop.visit_notes = request.form.get('visit_notes', '').strip() or None
        coming = request.form.get('answer') == 'yes'
        stop.confirmed_at = datetime.now() if coming else None
        stop.declined_at = None if coming else datetime.now()
        db.session.commit()
        return render_template('confirmed.html', stop=stop, coming=coming, business=_business())

    return render_template('confirm.html', stop=stop, customer=customer, animals=ANIMALS,
                           selected=[a.strip() for a in (customer.animals or '').split(',')],
                           business=_business())


@public.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user, remember=True)
            next_url = request.args.get('next', '')
            # Only follow relative redirects
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = url_for('admin.index')
            return redirect(next_url)
        flash('Wrong username or password.')
    return render_template('login.html', business=_business())


@public.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('public.login'))
