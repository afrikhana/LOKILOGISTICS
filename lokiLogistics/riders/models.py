from datetime import datetime
from lokiLogistics.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class Rider(db.Model):
    __tablename__ = 'riders'

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(50), default='motorcycle')
    vehicle_plate = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=True)
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Relationships
    merchant = db.relationship('Merchant', back_populates='riders')
    shipments = db.relationship('Shipment', backref='rider', lazy=True)
    history = db.relationship(
        'RiderHistory',
        backref='rider',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='RiderHistory.created_at.desc()',
    )


class RiderHistory(db.Model):
    __tablename__ = 'rider_history'

    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('riders.id'), nullable=False)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Fixed trailing comma