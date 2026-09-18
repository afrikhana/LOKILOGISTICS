from datetime import datetime
from lokiLogistics.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Relationships
    merchant = db.relationship('Merchant', back_populates='customers')
    shipments = db.relationship('Shipment', backref='customer', lazy=True)
    addresses = db.relationship('CustomerAddress', backref='customer', lazy=True, cascade="all, delete-orphan")


class CustomerAddress(db.Model):
    __tablename__ = 'customer_addresses'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    label = db.Column(db.String(50), default='Home')
    address = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    history = db.relationship('CustomerAddressHistory', backref='customer_address', lazy=True, cascade="all, delete-orphan")


class CustomerAddressHistory(db.Model):
    __tablename__ = 'customer_address_history'

    id = db.Column(db.Integer, primary_key=True)
    address_id = db.Column(db.Integer, db.ForeignKey('customer_addresses.id'), nullable=False)
    label = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)