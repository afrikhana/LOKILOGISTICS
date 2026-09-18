# -*- coding: utf-8 -*-
"""Authentication endpoints for lokiLogistics."""

from flask import Blueprint, request, jsonify
from lokiLogistics.extensions import db
from lokiLogistics.merchants.models import Merchant
from lokiLogistics.customers.models import Customer
from lokiLogistics.riders.models import Rider
# Import Admin model if stored separately
# from lokiLogistics.admins.models import Admin
from lokiLogistics.jwt.tokens import generate_access_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    role = data.get("role")
    password = data.get("password")

    if not role or not password:
        return jsonify({"error": "Role and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long"}), 400

    if role == "merchant":
        business_name = data.get("business_name")
        email = data.get("email")
        phone = data.get("phone")

        if not business_name or not email or not phone:
            return jsonify({"error": "business_name, email, and phone are required"}), 400

        if Merchant.query.filter_by(email=email).first():
            return jsonify({"error": "Merchant with this email already exists"}), 400

        user = Merchant(business_name=business_name, email=email, phone=phone)
        user.set_password(password)

    elif role == "customer":
        full_name = data.get("full_name")
        email = data.get("email")
        phone = data.get("phone")
        merchant_id = data.get("merchant_id")

        if not full_name or not email or not phone:
            return jsonify({"error": "full_name, email, and phone are required"}), 400

        if Customer.query.filter_by(email=email).first():
            return jsonify({"error": "Customer with this email already exists"}), 400

        user = Customer(
            full_name=full_name,
            email=email,
            phone=phone,
            merchant_id=merchant_id
        )
        user.set_password(password)

    elif role == "rider":
        full_name = data.get("full_name")
        phone = data.get("phone")
        merchant_id = data.get("merchant_id")
        vehicle_type = data.get("vehicle_type", "motorcycle")
        vehicle_plate = data.get("vehicle_plate")

        if not full_name or not phone:
            return jsonify({"error": "full_name and phone are required"}), 400

        if Rider.query.filter_by(phone=phone).first():
            return jsonify({"error": "Rider with this phone number already exists"}), 400

        user = Rider(
            full_name=full_name,
            phone=phone,
            merchant_id=merchant_id,
            vehicle_type=vehicle_type,
            vehicle_plate=vehicle_plate
        )
        user.set_password(password)

    # Add Admin block if admin registration is allowed via API
    # elif role == "admin":
    #     ...

    else:
        return jsonify({"error": "Invalid role specified"}), 400

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": f"{role.capitalize()} registered successfully",
        "entity_id": user.id,
        "role": role
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    role = data.get("role")
    identifier = data.get("identifier")
    password = data.get("password")

    if not role or not identifier or not password:
        return jsonify({"error": "Role, identifier, and password are required"}), 400

    user = None

    if role == "merchant":
        user = Merchant.query.filter_by(email=identifier).first()
    elif role == "customer":
        user = Customer.query.filter_by(email=identifier).first()
    elif role == "rider":
        user = Rider.query.filter_by(phone=identifier).first()
    # elif role == "admin":
    #     user = Admin.query.filter_by(email=identifier).first()
    else:
        return jsonify({"error": "Invalid role specified"}), 400

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_access_token(entity_id=user.id, role=role)

    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "entity_id": user.id,
        "role": role
    }), 200