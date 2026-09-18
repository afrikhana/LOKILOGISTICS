# -*- coding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import FloatField, IntegerField, StringField
from wtforms.validators import DataRequired, Length, Optional
from marshmallow import fields, pre_load, EXCLUDE
from lokiLogistics.extensions import ma
from .models import Order, Shipment, ShipmentHistory


# ==========================================
# WTFORMS
# ==========================================

class CreateCustomerOrderForm(FlaskForm):
    shop_id = IntegerField('Shop ID', validators=[DataRequired()])
    total_amount = FloatField('Total Amount', validators=[DataRequired()])
    delivery_lat = FloatField('Delivery Lat', validators=[DataRequired()])
    delivery_lng = FloatField('Delivery Lng', validators=[DataRequired()])


class CreateShipmentForm(FlaskForm):
    order_id = IntegerField('Order ID', validators=[DataRequired()])
    customer_id = IntegerField('Customer ID', validators=[DataRequired()])
    shop_id = IntegerField('Shop ID', validators=[DataRequired()])
    merchant_id = IntegerField('Merchant ID', validators=[DataRequired()])
    pickup_lat = FloatField('Pickup Lat', validators=[DataRequired()])
    pickup_lng = FloatField('Pickup Lng', validators=[DataRequired()])
    delivery_lat = FloatField('Delivery Lat', validators=[DataRequired()])
    delivery_lng = FloatField('Delivery Lng', validators=[DataRequired()])


class SetPickupOTPForm(FlaskForm):
    pickup_otp = StringField('Pickup OTP', validators=[DataRequired(), Length(min=4, max=6)])


class SetDeliveryOTPForm(FlaskForm):
    delivery_otp = StringField('Delivery OTP', validators=[DataRequired(), Length(min=4, max=6)])


# ==========================================
# MARSHMALLOW SCHEMAS
# ==========================================

class OrderSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Order
        load_instance = True
        include_fk = True
        unknown = EXCLUDE
        dump_only = ('id', 'order_number', 'created_at', 'updated_at')


class ShipmentHistorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ShipmentHistory
        load_instance = True
        include_fk = True


class ShipmentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Shipment
        load_instance = True
        include_fk = True   # Enables foreign key fields like order_id, merchant_id
        unknown = EXCLUDE
        dump_only = (
            'id', 
            'tracking_number', 
            'created_at', 
            'updated_at', 
            'merchant_id', 
            'shop_id', 
            'pickup_otp', 
            'delivery_otp'
        )


class ShipmentDetailSchema(ma.SQLAlchemyAutoSchema):
    """Schema for detailed shipment response including order details and audit history."""
    order = ma.Nested(OrderSchema, dump_only=True)
    history = ma.Nested(ShipmentHistorySchema, many=True, dump_only=True)

    class Meta:
        model = Shipment
        load_instance = True
        include_fk = True


class TelemetryWebhookSchema(ma.Schema):
    """Accepts both compact ('t', 'lat', 'lng') and verbose telemetry keys to save bandwidth."""
    t = fields.Str(data_key='t', required=False)
    tracking_number = fields.Str(data_key='tracking_number', required=False)
    lat = fields.Float(required=True)
    lng = fields.Float(required=True)

    @pre_load
    def normalize_keys(self, data, **kwargs):
        # Map compact key 't' to 'tracking_number' if supplied
        if isinstance(data, dict):
            if 't' in data and 'tracking_number' not in data:
                data['tracking_number'] = data['t']
        return data