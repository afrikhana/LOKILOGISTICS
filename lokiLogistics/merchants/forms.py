# -*- coding: utf-8 -*-
"""Merchant forms and schemas."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, FloatField
from wtforms.validators import DataRequired, Email, Length, Optional
from lokiLogistics.extensions import ma
from .models import Merchant, Shop, ShopHistory


# --- WTForms ---
class MerchantRegistrationForm(FlaskForm):
    business_name = StringField('Business Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])


class MerchantUpdateForm(FlaskForm):
    business_name = StringField('Business Name', validators=[Optional(), Length(max=120)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])


class ShopForm(FlaskForm):
    name = StringField('Shop Name', validators=[DataRequired(), Length(max=100)])
    address = StringField('Address', validators=[DataRequired(), Length(max=255)])
    lat = FloatField('Latitude', validators=[DataRequired()])
    lng = FloatField('Longitude', validators=[DataRequired()])


# --- Marshmallow Schemas ---
class ShopHistorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ShopHistory
        load_instance = True
        include_fk = True


class ShopSchema(ma.SQLAlchemyAutoSchema):
    history = ma.Nested(ShopHistorySchema, many=True, dump_only=True)

    class Meta:
        model = Shop
        load_instance = True
        include_fk = True


class MerchantDetailSchema(ma.SQLAlchemyAutoSchema):
    shops = ma.Nested(ShopSchema, many=True, dump_only=True)

    class Meta:
        model = Merchant
        load_instance = True
        exclude = ("password_hash",)


class MerchantSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Merchant
        load_instance = True
        exclude = ("password_hash",)