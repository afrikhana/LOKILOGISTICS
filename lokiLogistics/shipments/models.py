# -*- coding: utf-8 -*-
from datetime import datetime
import random
import uuid
from lokiLogistics.extensions import db


def generate_otp_code():
    """Generates a default 4-digit OTP string."""
    return f"{random.randint(1000, 9999)}"


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )

    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)

    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_status = db.Column(db.String(20), default='PENDING', nullable=False)
    status = db.Column(db.String(50), default='CONFIRMED', nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 1-to-1 relationship with Shipment
    shipment = db.relationship('Shipment', backref='order', uselist=False, cascade='all, delete-orphan')


class Shipment(db.Model):
    __tablename__ = 'shipments'

    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )

    # Foreign Keys
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    rider_id = db.Column(db.Integer, db.ForeignKey('riders.id'), nullable=True)

    # Status: PENDING, RIDER_ASSIGNED, IN_TRANSIT, DELIVERED, CANCELLED
    status = db.Column(db.String(50), nullable=False, default='PENDING')

    # OTP Management
    pickup_otp = db.Column(db.String(6), default=generate_otp_code, nullable=True)
    delivery_otp = db.Column(db.String(6), default=generate_otp_code, nullable=True)

    pickup_attempts = db.Column(db.Integer, default=0, nullable=False)
    delivery_attempts = db.Column(db.Integer, default=0, nullable=False)

    # Route Coordinates
    pickup_lat = db.Column(db.Float, nullable=False)
    pickup_lng = db.Column(db.Float, nullable=False)
    delivery_lat = db.Column(db.Float, nullable=False)
    delivery_lng = db.Column(db.Float, nullable=False)

    # Live Telemetry
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    history = db.relationship(
        'ShipmentHistory',
        backref='shipment',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='ShipmentHistory.created_at.desc()',
    )


class ShipmentHistory(db.Model):
    __tablename__ = 'shipment_history'

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.id'), nullable=False)

    status = db.Column(db.String(50), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)