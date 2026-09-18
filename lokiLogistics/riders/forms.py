# -*- coding: utf-8 -*-
"""Rider forms and schemas for lokiLogistics."""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, FloatField, PasswordField
from wtforms.validators import DataRequired, Optional, Length
from lokiLogistics.extensions import ma
from lokiLogistics.riders.models import Rider, RiderHistory

# --- WTForms ---
class RiderForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    vehicle_type = SelectField(
        'Vehicle Type',
        choices=[('motorcycle', 'Motorcycle'), ('van', 'Van'), ('bicycle', 'Bicycle')]
    )
    vehicle_plate = StringField('Vehicle Plate', validators=[Optional(), Length(max=20)])
    merchant_id = IntegerField('Merchant ID', validators=[Optional()])


class RiderUpdateForm(FlaskForm):
    full_name = StringField('Full Name', validators=[Optional(), Length(max=100)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])
    vehicle_type = SelectField(
        'Vehicle Type',
        choices=[('motorcycle', 'Motorcycle'), ('van', 'Van'), ('bicycle', 'Bicycle')],
        validators=[Optional()]
    )
    vehicle_plate = StringField('Vehicle Plate', validators=[Optional(), Length(max=20)])
    is_active = BooleanField('Is Active', validators=[Optional()])
    is_available = BooleanField('Is Available', validators=[Optional()])
    merchant_id = IntegerField('Merchant ID', validators=[Optional()])


class VerifyOTPForm(FlaskForm):
    shipment_id = IntegerField('Shipment ID', validators=[DataRequired()])
    otp = StringField('OTP Code', validators=[DataRequired(), Length(min=4, max=6)])
    lat = FloatField('Latitude', validators=[Optional()])
    lng = FloatField('Longitude', validators=[Optional()])


# --- Marshmallow Schemas ---
class RiderHistorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = RiderHistory
        load_instance = True
        include_fk = True


class RiderSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Rider
        load_instance = True
        include_fk = True
        exclude = ("password_hash",)


class RiderDetailSchema(ma.SQLAlchemyAutoSchema):
    history = ma.Nested(RiderHistorySchema, many=True, dump_only=True)

    class Meta:
        model = Rider
        load_instance = True
        include_fk = True
        exclude = ("password_hash",)