import re
import secrets
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

ANIMALS = ['Alpaca', 'Llama', 'Sheep', 'Goat', 'Pig', 'Other']


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Area(db.Model):
    """Maps a zip prefix ("925") or full zip ("92562") to an area. Longest match wins."""
    id = db.Column(db.Integer, primary_key=True)
    zip_prefix = db.Column(db.String(5), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    def __str__(self):
        return f'{self.zip_prefix} → {self.name}'


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(30))
    zip_code = db.Column(db.String(5))
    area = db.Column(db.String(100), default='Unassigned', index=True)
    animals = db.Column(db.String(200))
    notes = db.Column(db.Text)

    stops = db.relationship('Stop', back_populates='customer', cascade='all, delete-orphan')

    def __str__(self):
        return self.name


class Trip(db.Model):
    """One run through an area, e.g. Riverside / Temecula, Oct 20–22."""
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    area = db.Column(db.String(100), nullable=False)
    dates = db.Column(db.String(100), nullable=False)  # free text: "Oct 20–22"

    stops = db.relationship('Stop', back_populates='trip', cascade='all, delete-orphan')

    def __str__(self):
        return f'{self.area} — {self.dates}'


class Stop(db.Model):
    """A customer on a trip, and how far along they are."""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(16))
    projected_sent_at = db.Column(db.DateTime)
    firm_sent_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)
    declined_at = db.Column(db.DateTime)
    visit_notes = db.Column(db.Text)

    trip = db.relationship('Trip', back_populates='stops')
    customer = db.relationship('Customer', back_populates='stops')

    __table_args__ = (db.UniqueConstraint('trip_id', 'customer_id'),)


def clean_zip(value):
    match = re.search(r'\d{5}', value or '')
    return match.group(0) if match else None


def area_for_zip(zip_code):
    if not zip_code:
        return 'Unassigned'
    matches = [a for a in Area.query.all() if zip_code.startswith(a.zip_prefix)]
    if not matches:
        return 'Unassigned'
    return max(matches, key=lambda a: len(a.zip_prefix)).name


def reassign_all_areas():
    for customer in Customer.query.all():
        customer.area = area_for_zip(customer.zip_code)
    db.session.commit()
