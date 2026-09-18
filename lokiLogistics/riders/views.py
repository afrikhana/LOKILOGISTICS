# -*- coding: utf-8 -*-
"""Rider endpoints for lokiLogistics."""

import random
from flask import Blueprint, request, jsonify
from lokiLogistics.extensions import db
from lokiLogistics.utils import publish_location_ping
from lokiLogistics.riders.models import Rider, RiderHistory
from lokiLogistics.riders.forms import (
    RiderSchema,
    RiderDetailSchema,
    RiderHistorySchema,
    VerifyOTPForm,
)
from lokiLogistics.shipments.models import Shipment, ShipmentHistory
from lokiLogistics.extensions import redis_client
from lokiLogistics.jwt.tokens import token_required

riders_bp = Blueprint('riders', __name__, url_prefix='/api/riders')

rider_schema = RiderSchema()
rider_detail_schema = RiderDetailSchema()
riders_detail_schema = RiderDetailSchema(many=True)
rider_history_schema = RiderHistorySchema(many=True)

MAX_OTP_ATTEMPTS = 5


def _generate_4digit_code():
    return f"{random.randint(1000, 9999)}"


# ==========================================
# RIDER CRUD ENDPOINTS
# ==========================================

@riders_bp.route('', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def create_rider(current_identity):
    data = request.get_json() or {}

    if current_identity['role'] == 'merchant':
        data['merchant_id'] = current_identity['id']

    password = data.pop('password', None)
    rider = rider_schema.load(data)

    if password:
        rider.set_password(password)

    db.session.add(rider)
    db.session.commit()
    return rider_detail_schema.dump(rider), 201


@riders_bp.route('', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin'])
def get_riders(current_identity):
    is_available = request.args.get('is_available', type=lambda v: v.lower() == 'true')
    query = Rider.query

    if current_identity['role'] == 'merchant':
        query = query.filter_by(merchant_id=current_identity['id'])
    else:
        merchant_id = request.args.get('merchant_id', type=int)
        if merchant_id:
            query = query.filter_by(merchant_id=merchant_id)

    if is_available is not None:
        query = query.filter_by(is_available=is_available)

    riders = query.all()
    return jsonify(riders_detail_schema.dump(riders)), 200


@riders_bp.route('/<int:id>', methods=['GET'])
@token_required(allowed_roles=['rider', 'merchant', 'admin'])
def get_rider(current_identity, id):
    rider = Rider.query.get_or_404(id)

    if current_identity['role'] == 'rider' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only view your own profile"}), 403

    if current_identity['role'] == 'merchant' and rider.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Rider does not belong to your account"}), 403

    return rider_detail_schema.dump(rider), 200


@riders_bp.route('/<int:id>', methods=['PUT', 'PATCH'])
@token_required(allowed_roles=['rider', 'merchant', 'admin'])
def update_rider(current_identity, id):
    rider = Rider.query.get_or_404(id)

    if current_identity['role'] == 'rider' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only update your own credentials"}), 403

    if current_identity['role'] == 'merchant' and rider.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Rider does not belong to your account"}), 403

    data = request.get_json() or {}

    if 'password' in data:
        rider.set_password(data.pop('password'))

    for key, value in data.items():
        if hasattr(rider, key) and key not in ['id', 'created_at', 'password_hash', 'merchant_id']:
            setattr(rider, key, value)

    db.session.commit()
    return rider_detail_schema.dump(rider), 200


@riders_bp.route('/<int:id>', methods=['DELETE'])
@token_required(allowed_roles=['merchant', 'admin'])
def delete_rider(current_identity, id):
    rider = Rider.query.get_or_404(id)

    if current_identity['role'] == 'merchant' and rider.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Rider does not belong to your account"}), 403

    db.session.delete(rider)
    db.session.commit()
    return jsonify({"message": f"Rider {id} deleted successfully"}), 200


# ==========================================
# CLAIM SHIPMENT & OTP VERIFICATION ENDPOINTS
# ==========================================

@riders_bp.route('/<int:id>/claim-shipment', methods=['POST'])
@token_required(allowed_roles=['rider', 'admin'])
def claim_shipment(current_identity, id):
    """Allows an active rider to claim an open pending shipment."""
    if current_identity['role'] == 'rider' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only claim shipments for your own account"}), 403

    rider = Rider.query.get_or_404(id)
    if not rider.is_available:
        return jsonify({"error": "Rider is currently busy with another active delivery"}), 400

    data = request.get_json() or {}
    shipment_id = data.get('shipment_id')
    if not shipment_id:
        return jsonify({"error": "shipment_id is required"}), 400

    shipment = Shipment.query.get_or_404(shipment_id)

    if shipment.rider_id is not None:
        return jsonify({"error": "Shipment has already been claimed or assigned to another rider"}), 409

    if shipment.status not in ['PENDING', 'CONFIRMED']:
        return jsonify({"error": f"Cannot claim shipment with status '{shipment.status}'"}), 400

    shipment.rider_id = rider.id
    rider.is_available = False

    rider_history = RiderHistory(
        rider_id=rider.id,
        shipment_id=shipment.id,
        action='SHIPMENT_CLAIMED',
        lat=rider.current_lat,
        lng=rider.current_lng,
        notes=f'Shipment #{shipment.id} claimed by Rider #{rider.id}'
    )
    shipment_history = ShipmentHistory(
        shipment_id=shipment.id,
        status=shipment.status,
        lat=rider.current_lat,
        lng=rider.current_lng,
        notes=f'Claimed by Rider #{rider.id}'
    )

    db.session.add(rider_history)
    db.session.add(shipment_history)
    db.session.commit()

    return jsonify({
        "message": "Shipment claimed successfully",
        "shipment_id": shipment.id,
        "rider_id": rider.id
    }), 200


@riders_bp.route('/<int:id>/verify-pickup', methods=['POST'])
@token_required(allowed_roles=['rider', 'admin'])
def verify_pickup_otp(current_identity, id):
    if current_identity['role'] == 'rider' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only verify pickups assigned to your account"}), 403

    rider = Rider.query.get_or_404(id)
    data = request.get_json() or {}

    shipment_id = data.get('shipment_id')
    otp_input = str(data.get('otp', '')).strip()

    # Fixed: Query by rider_id instead of duplicate id
    shipment = Shipment.query.filter_by(id=shipment_id, rider_id=rider.id).first_or_404()

    if shipment.pickup_attempts >= MAX_OTP_ATTEMPTS:
        return jsonify({"error": "Max pickup OTP attempts reached. Merchant override required."}), 429

    if shipment.pickup_otp != otp_input:
        shipment.pickup_attempts += 1
        db.session.commit()
        remaining = MAX_OTP_ATTEMPTS - shipment.pickup_attempts
        return jsonify({"error": f"Invalid pickup OTP. {remaining} attempts remaining."}), 400

    shipment.status = 'IN_TRANSIT'
    shipment.delivery_otp = _generate_4digit_code()
    shipment.pickup_attempts = 0
    rider.is_available = False

    rider_history = RiderHistory(
        rider_id=rider.id,
        shipment_id=shipment.id,
        action='PICKUP_OTP_VERIFIED',
        lat=data.get('lat'),
        lng=data.get('lng'),
        notes='Pickup verified via OTP'
    )
    shipment_history = ShipmentHistory(
        shipment_id=shipment.id,
        status='IN_TRANSIT',
        lat=data.get('lat'),
        lng=data.get('lng'),
        notes=f'Picked up by Rider {rider.id}'
    )

    db.session.add(rider_history)
    db.session.add(shipment_history)
    db.session.commit()

    return jsonify({"message": "Pickup OTP verified. Shipment in transit.", "shipment_id": shipment.id}), 200


@riders_bp.route('/<int:id>/verify-delivery', methods=['POST'])
@token_required(allowed_roles=['rider', 'admin'])
def verify_delivery_otp(current_identity, id):
    if current_identity['role'] == 'rider' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only verify deliveries assigned to your account"}), 403

    rider = Rider.query.get_or_404(id)
    data = request.get_json() or {}

    shipment_id = data.get('shipment_id')
    otp_input = str(data.get('otp', '')).strip()

    # Fixed: Query by rider_id instead of duplicate id
    shipment = Shipment.query.filter_by(id=shipment_id, rider_id=rider.id).first_or_404()

    if shipment.delivery_attempts >= MAX_OTP_ATTEMPTS:
        return jsonify({"error": "Max delivery OTP attempts required. Support intervention required."}), 429

    if shipment.delivery_otp != otp_input:
        shipment.delivery_attempts += 1
        db.session.commit()
        remaining = MAX_OTP_ATTEMPTS - shipment.delivery_attempts
        return jsonify({"error": f"Invalid delivery OTP. {remaining} attempts remaining."}), 400

    shipment.status = 'DELIVERED'
    shipment.delivery_attempts = 0
    rider.is_available = True

    rider_history = RiderHistory(
        rider_id=rider.id,
        shipment_id=shipment.id,
        action='DELIVERY_OTP_VERIFIED',
        lat=data.get('lat'),
        lng=data.get('lng'),
        notes='Delivery verified via OTP'
    )
    shipment_history = ShipmentHistory(
        shipment_id=shipment.id,
        status='DELIVERED',
        lat=data.get('lat'),
        lng=data.get('lng'),
        notes=f'Delivered successfully by Rider {rider.id}'
    )

    db.session.add(rider_history)
    db.session.add(shipment_history)
    db.session.commit()

    return jsonify({"message": "Delivery OTP verified. Shipment completed.", "shipment_id": shipment.id}), 200


@riders_bp.route('/<int:id>/history', methods=['GET'])
@token_required(allowed_roles=['rider', 'merchant', 'admin'])
def get_rider_history(current_identity, id):
    rider = Rider.query.get_or_404(id)

    if current_identity['role'] == 'rider' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only view your own history"}), 403

    if current_identity['role'] == 'merchant' and rider.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Rider does not belong to your account"}), 403

    history = RiderHistory.query.filter_by(rider_id=rider.id).order_by(RiderHistory.created_at.desc()).all()
    return jsonify(rider_history_schema.dump(history)), 200


Python

# ==========================================
# TELEMETRY & LOCATION ENDPOINTS
# ==========================================
@riders_bp.route('/<int:rider_id>/location', methods=['POST'])
@token_required(allowed_roles=['rider'])
def update_rider_location(rider_id):
    data = request.get_json() or {}
    
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
    except (ValueError, TypeError):
        return jsonify({"error": "Valid lat and lng floats are required"}), 400

    # 1. Cache raw rider position for proximity/dispatch lookup
    redis_client.hset(f"rider:{rider_id}:location", mapping={"lat": lat, "lng": lng})

    # 2. Check if rider is currently executing an active delivery
    active_shipment = Shipment.query.filter_by(
        rider_id=rider_id, 
        status='IN_TRANSIT'
    ).first()

    # 3. Stream position to consumer/merchant SSE clients
    if active_shipment:
        publish_location_ping(active_shipment.id, lat, lng, active_shipment.status)

    return '', 204