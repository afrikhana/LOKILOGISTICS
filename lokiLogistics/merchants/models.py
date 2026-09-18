from datetime import datetime
from lokiLogistics.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class Merchant(db.Model):
    __tablename__ = 'merchants'

    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Explicit back_populates cleanly references both ends without duplicate declaration
    shops = db.relationship('Shop', backref='merchant', lazy=True, cascade="all, delete-orphan")
    riders = db.relationship('Rider', back_populates='merchant', lazy=True)
    customers = db.relationship('Customer', back_populates='merchant', lazy=True)


class Shop(db.Model):
    __tablename__ = 'shops'

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    history = db.relationship('ShopHistory', backref='shop', lazy=True, cascade="all, delete-orphan")
    shipments = db.relationship('Shipment', backref='shop', lazy=True)


class ShopHistory(db.Model):
    __tablename__ = 'shop_history'

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)  # Fixed trailing comma