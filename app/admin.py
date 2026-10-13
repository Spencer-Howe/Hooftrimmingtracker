from datetime import datetime

from flask import flash, redirect, request, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from flask_login import current_user
from sqlalchemy import func, inspect

from .extensions import db
from .models import Area, Customer, Stop, Trip, area_for_zip, clean_zip, reassign_all_areas
from .trips import (FIRM_BODY, FIRM_SUBJECT, PROJECTED_BODY, PROJECTED_SUBJECT, send_step,
                    stop_status, sync_stops)


class SecureMixin:
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('public.login', next=request.full_path))


class TripsView(SecureMixin, AdminIndexView):
    """Home page: plan a trip, list past/upcoming trips, open one to run it."""

    @expose('/')
    def index(self):
        areas = (db.session.query(Customer.area, func.count(Customer.id))
                 .group_by(Customer.area).order_by(Customer.area).all())
        trips = Trip.query.order_by(Trip.created_at.desc()).all()
        return self.render('admin/trips.html', areas=areas, trips=trips)

    @expose('/trip/new', methods=['POST'])
    def create(self):
        area, dates = request.form.get('area', '').strip(), request.form.get('dates', '').strip()
        if not area or not dates:
            flash('Pick an area and type the dates.', 'error')
            return redirect(url_for('.index'))
        trip = Trip(area=area, dates=dates)
        db.session.add(trip)
        db.session.commit()
        sync_stops(trip)
        return redirect(url_for('.trip', trip_id=trip.id))

    @expose('/trip/<int:trip_id>')
    def trip(self, trip_id):
        trip = db.get_or_404(Trip, trip_id)
        sync_stops(trip)
        stops = sorted(trip.stops, key=lambda s: s.customer.name.lower())
        confirmed = [s for s in stops if s.confirmed_at]
        others = [s for s in stops if not s.confirmed_at]
        return self.render(
            'admin/trip.html', trip=trip, confirmed=confirmed, others=others, status=stop_status,
            projected_done=all(s.projected_sent_at or not s.customer.email for s in stops),
            firm_done=all(s.firm_sent_at or s.confirmed_at or s.declined_at or not s.customer.email
                          for s in stops),
            defaults={'projected': (PROJECTED_SUBJECT, PROJECTED_BODY), 'firm': (FIRM_SUBJECT, FIRM_BODY)})

    @expose('/trip/<int:trip_id>/dates', methods=['POST'])
    def update_dates(self, trip_id):
        trip = db.get_or_404(Trip, trip_id)
        trip.dates = request.form.get('dates', '').strip() or trip.dates
        db.session.commit()
        return redirect(url_for('.trip', trip_id=trip.id))

    @expose('/trip/<int:trip_id>/send/<step>', methods=['POST'])
    def send(self, trip_id, step):
        trip = db.get_or_404(Trip, trip_id)
        if step not in ('projected', 'firm'):
            return redirect(url_for('.trip', trip_id=trip.id))
        subject, body = request.form.get('subject', '').strip(), request.form.get('body', '').strip()
        if not subject or not body:
            flash('Add a subject and message.', 'error')
            return redirect(url_for('.trip', trip_id=trip.id))
        sent, failed = send_step(trip, step, subject, body)
        flash(f'Sent {sent} emails.', 'success')
        if failed:
            flash(f'{failed} did not send — check the Gmail settings or daily limit, then press send '
                  'again (it only sends to people who haven\'t gotten it).', 'error')
        return redirect(url_for('.trip', trip_id=trip.id))

    @expose('/stop/<int:stop_id>/<answer>', methods=['POST'])
    def mark(self, stop_id, answer):
        """For customers who confirm by text or phone instead of the link."""
        stop = db.get_or_404(Stop, stop_id)
        stop.confirmed_at = datetime.now() if answer == 'yes' else None
        stop.declined_at = datetime.now() if answer == 'no' else None
        db.session.commit()
        return redirect(url_for('.trip', trip_id=stop.trip_id))


class CustomerView(SecureMixin, ModelView):
    page_size = 100
    can_export = True  # her list is hers: Export -> CSV
    export_types = ['csv']
    column_export_list = ['name', 'email', 'phone', 'zip_code', 'area', 'animals', 'notes', 'created_at']
    column_list = ['name', 'area', 'zip_code', 'animals', 'phone', 'email', 'notes']
    column_default_sort = 'name'
    column_searchable_list = ['name', 'email', 'phone', 'zip_code', 'animals', 'notes', 'area']
    column_filters = ['area']
    column_labels = {'zip_code': 'Zip'}
    form_columns = ['name', 'email', 'phone', 'zip_code', 'animals', 'notes']
    form_widget_args = {'notes': {'rows': 4}}

    def on_model_change(self, form, model, is_created):
        if is_created or inspect(model).attrs.zip_code.history.has_changes():
            model.zip_code = clean_zip(model.zip_code)
            model.area = area_for_zip(model.zip_code)


class AreaView(SecureMixin, ModelView):
    column_list = ['zip_prefix', 'name']
    column_labels = {'zip_prefix': 'Zip or zip prefix', 'name': 'Area'}
    column_default_sort = 'zip_prefix'
    column_descriptions = {
        'zip_prefix': 'First 3 digits covers a region ("925"); a full zip ("92562") overrides it.',
    }

    def on_model_change(self, form, model, is_created):
        model.zip_prefix = ''.join(ch for ch in model.zip_prefix if ch.isdigit())[:5]

    def after_model_change(self, form, model, is_created):
        reassign_all_areas()

    def after_model_delete(self, model):
        reassign_all_areas()


def setup_admin(app):
    admin = Admin(app, name=app.config['BUSINESS_NAME'], index_view=TripsView(name='Trips'),
                  template_mode='bootstrap4')
    admin.add_view(CustomerView(Customer, db.session, name='Customers'))
    admin.add_view(AreaView(Area, db.session, name='Areas'))
    admin.add_link(MenuLink(name='Sign-up Page', url='/'))
    admin.add_link(MenuLink(name='Log out', url='/logout'))
    return admin
