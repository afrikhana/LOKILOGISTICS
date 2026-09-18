# -*- coding: utf-8 -*-
"""Customer forms and schemas."""
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Email, Optional, Length
from lokiLogistics.extensions import ma
from .models import Customer, CustomerAddress, CustomerAddressHistory

# --- WTForms ---
class CustomerForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    merchant_id = IntegerField('Merchant ID', validators=[Optional()])


class CustomerUpdateForm(FlaskForm):
    full_name = StringField('Full Name', validators=[Optional(), Length(max=100)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])
    merchant_id = IntegerField('Merchant ID', validators=[Optional()])


class CustomerAddressForm(FlaskForm):
    label = StringField('Label', validators=[Optional(), Length(max=50)])
    address = StringField('Address', validators=[DataRequired(), Length(max=255)])
    lat = FloatField('Latitude', validators=[DataRequired()])
    lng = FloatField('Longitude', validators=[DataRequired()])
    is_default = BooleanField('Default Address', validators=[Optional()])


# --- Marshmallow Schemas ---
class CustomerAddressHistorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = CustomerAddressHistory
        load_instance = True
        include_fk = True


class CustomerAddressSchema(ma.SQLAlchemyAutoSchema):
    history = ma.Nested(CustomerAddressHistorySchema, many=True, dump_only=True)

    class Meta:
        model = CustomerAddress
        load_instance = True
        include_fk = True


class CustomerDetailSchema(ma.SQLAlchemyAutoSchema):
    addresses = ma.Nested(CustomerAddressSchema, many=True, dump_only=True)

    class Meta:
        model = Customer
        load_instance = True
        include_fk = True
        exclude = ("password_hash",)


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Customer
        load_instance = True
        include_fk = True
        exclude = ("password_hash",)