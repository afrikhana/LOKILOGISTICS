# -*- coding: utf-8 -*-
"""Shipment routes and telemetry handlers for lokiLogistics."""

import json
import random
from flask import Blueprint, request, jsonify, Response, g
from lokiLogistics.extensions import db, redis_client
from lokiLogistics.merchants.models import Shop
from lokiLogistics.shipments.models import Order, Shipment, ShipmentHistory
from lokiLogistics.shipments.forms import (
    ShipmentSchema,
    ShipmentDetailSchema,
    ShipmentHistorySchema,
    TelemetryWebhookSchema,
    CreateCustomerOrderForm
)
from lokiLogistics.jwt.tokens import token_required

shipments_bp = Blueprint('shipments', __name__, url_prefix='/api/shipments')

shipment_schema = ShipmentSchema()
shipment_detail_schema = ShipmentDetailSchema()
shipments_detail_schema = ShipmentDetailSchema(many=True)
shipment_history_schema = ShipmentHistorySchema(many=True)
telemetry_schema = TelemetryWebhookSchema()


def _generate_4digit_code():
    return f"{random.randint(1000, 9999)}"


# ==========================================
# CUSTOMER AUTOMATED ORDER & SHIPMENT CREATION
# ==========================================

def create_shipment_for_order(order, pickup_lat, pickup_lng, delivery_lat, delivery_lng):
    """Internal helper to create a shipment linked to an order."""
    shipment = Shipment(
        order_id=order.id,
        merchant_id=order.merchant_id,
        shop_id=order.shop_id,
        customer_id=order.customer_id,
        status='PENDING',
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        delivery_lat=delivery_lat,
        delivery_lng=delivery_lng,
        pickup_otp=_generate_4digit_code(),
        delivery_otp=_generate_4digit_code()
    )
    db.session.add(shipment)
    db.session.flush()

    history = ShipmentHistory(
        shipment_id=shipment.id,
        status='PENDING',
        lat=pickup_lat,
        lng=pickup_lng,
        notes=f'Auto-created from Order #{order.id}'
    )
    db.session.add(history)
    return shipment


@shipments_bp.route('/customer-order', methods=['POST'])
@token_required(allowed_roles=['customer'])
def create_customer_order():
    """Customer endpoint to place an order and automatically initiate shipment tracking."""
    data = request.get_json() or {}
    user = getattr(g, 'current_user', {})
    customer_id = user.get('id') or int(user.get('sub', 0))

    shop_id = data.get('shop_id')
    delivery_lat = data.get('delivery_lat')
    delivery_lng = data.get('delivery_lng')

    if not shop_id or delivery_lat is None or delivery_lng is None:
        return jsonify({"error": "shop_id, delivery_lat, and delivery_lng are required"}), 400

    # Look up Shop to extract ground-truth pickup coordinates and merchant_id
    shop = Shop.query.get(shop_id)
    if not shop:
        return jsonify({"error": "Shop not found"}), 404

    # 1. Create Order
    new_order = Order(
        customer_id=customer_id,
        merchant_id=shop.merchant_id,
        shop_id=shop.id,
        total_amount=data.get('total_amount', 0.0),
        status='CONFIRMED',
        payment_status='PAID'
    )
    db.session.add(new_order)
    db.session.flush()

    # 2. Auto-create Shipment using Shop coordinates
    shipment = create_shipment_for_order(
        order=new_order,
        pickup_lat=shop.lat,
        pickup_lng=shop.lng,
        delivery_lat=delivery_lat,
        delivery_lng=delivery_lng
    )

    db.session.commit()

    return jsonify({
        "message": "Order placed and shipment created successfully",
        "order_id": new_order.id,
        "shipment": shipment_detail_schema.dump(shipment)
    }), 201


# ==========================================
# OTP GENERATION
# ==========================================

@shipments_bp.route('/<int:id>/generate-pickup-otp', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def generate_pickup_otp(id):
    """Merchant endpoint to explicitly generate or reset a Pickup OTP."""
    shipment = Shipment.query.get_or_404(id)
    
    data = request.get_json() or {}
    otp = str(data.get('pickup_otp', '')).strip() or _generate_4digit_code()
    
    shipment.pickup_otp = otp
    shipment.pickup_attempts = 0
    db.session.commit()
    
    return jsonify({
        "message": "Pickup OTP updated successfully by Merchant",
        "shipment_id": shipment.id,
        "pickup_otp": shipment.pickup_otp
    }), 200


@shipments_bp.route('/<int:id>/generate-delivery-otp', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def generate_delivery_otp(id):
    """System endpoint triggered on dispatch to generate & send Delivery OTP to Customer."""
    shipment = Shipment.query.get_or_404(id)
    
    data = request.get_json() or {}
    otp = str(data.get('delivery_otp', '')).strip() or _generate_4digit_code()
    
    shipment.delivery_otp = otp
    shipment.delivery_attempts = 0
    db.session.commit()
    
    return jsonify({
        "message": "Delivery OTP generated and dispatched to Customer",
        "shipment_id": shipment.id
    }), 200


# ==========================================
# GET SHIPMENTS
# ==========================================

@shipments_bp.route('', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin', 'rider'])
def get_shipments():
    """Retrieve shipments filtered by role (merchants see only their own)."""
    user = getattr(g, 'current_user', {})
    user_role = user.get('role')
    user_id = user.get('id') or int(user.get('sub', 0))

    if user_role == 'merchant':
        shipments = Shipment.query.filter_by(merchant_id=user_id).all()
    else:
        shipments = Shipment.query.all()

    return jsonify(shipments_detail_schema.dump(shipments)), 200


@shipments_bp.route('/<int:id>', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin', 'rider'])
def get_shipment_by_id(id):
    """Retrieve a single shipment."""
    shipment = Shipment.query.get_or_404(id)
    return jsonify(shipment_detail_schema.dump(shipment)), 200


# ==========================================
# CREATE SHIPMENT & RIDER PICKUP
# ==========================================

@shipments_bp.route('', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def create_shipment():
    data = request.get_json() or {}
    data.pop('tracking_number', None)

    user = getattr(g, 'current_user', {})
    user_role = user.get('role')
    user_id = user.get('id') or int(user.get('sub', 0))

    if user_role == 'merchant':
        data['merchant_id'] = user_id
    elif user_role == 'admin' and 'merchant_id' not in data:
        data['merchant_id'] = data.get('merchant_id')

    if not data.get('merchant_id'):
        return jsonify({"error": "merchant_id is required to create a shipment"}), 400

    shipment = shipment_schema.load(data)

    if not shipment.pickup_otp:
        shipment.pickup_otp = _generate_4digit_code()

    db.session.add(shipment)
    db.session.flush()

    history_entry = ShipmentHistory(
        shipment_id=shipment.id,
        status=shipment.status,
        lat=shipment.pickup_lat,
        lng=shipment.pickup_lng,
        notes='Shipment registered'
    )
    db.session.add(history_entry)
    db.session.commit()

    return jsonify(shipment_detail_schema.dump(shipment)), 201


@shipments_bp.route('/<int:id>/pickup', methods=['POST'])
@token_required(allowed_roles=['rider', 'admin'])
def rider_pickup_shipment(id):
    """Rider confirms pickup using the Merchant's Pickup OTP."""
    shipment = Shipment.query.get_or_404(id)
    data = request.get_json() or {}
    provided_otp = str(data.get('pickup_otp', '')).strip()

    if shipment.pickup_otp != provided_otp:
        shipment.pickup_attempts = (shipment.pickup_attempts or 0) + 1
        db.session.commit()
        return jsonify({"error": "Invalid Pickup OTP"}), 400

    user = getattr(g, 'current_user', {})
    rider_id = user.get('id') or int(user.get('sub', 0))

    shipment.status = 'IN_TRANSIT'
    if hasattr(shipment, 'rider_id'):
        shipment.rider_id = rider_id

    history_entry = ShipmentHistory(
        shipment_id=shipment.id,
        status='IN_TRANSIT',
        lat=shipment.pickup_lat,
        lng=shipment.pickup_lng,
        notes=f'Goods picked up by Rider #{rider_id}'
    )
    db.session.add(history_entry)
    db.session.commit()

    return jsonify({
        "message": "Goods picked up successfully",
        "shipment": shipment_detail_schema.dump(shipment)
    }), 200


# ==========================================
# TELEMETRY & STREAMING
# ==========================================

@shipments_bp.route('/webhook/telemetry', methods=['POST'])
def handle_telemetry_webhook():
    """Ultra-lean endpoint optimized for Ngrok free tier bandwidth limits."""
    data = request.get_json() or {}
    
    tracking_number = data.get('t') or data.get('tracking_number')
    lat = data.get('lat')
    lng = data.get('lng')

    if not tracking_number or lat is None or lng is None:
        return '', 400

    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first()
    if not shipment or shipment.status in ['DELIVERED', 'CANCELLED']:
        return '', 204

    shipment.current_lat = lat
    shipment.current_lng = lng
    db.session.commit()
    
    return '', 204


@shipments_bp.route('/<int:shipment_id>/stream-location', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin', 'customer', 'rider'])
def stream_shipment_location(shipment_id):
    """
    Server-Sent Events (SSE) endpoint for tracking active delivery location.
    Establishes an HTTP chunked event-stream connected to Redis Pub/Sub.
    """
    shipment = Shipment.query.get_or_404(shipment_id)

    def event_generator():
        r = redis_client
        pubsub = r.pubsub()
        channel = f"shipment:{shipment_id}:stream"
        pubsub.subscribe(channel)

        initial_data = json.dumps({
            "shipment_id": shipment.id,
            "lat": shipment.current_lat or shipment.pickup_lat,
            "lng": shipment.current_lng or shipment.pickup_lng,
            "status": shipment.status
        })
        yield f"data: {initial_data}\n\n"

        for message in pubsub.listen():
            if message['type'] == 'message':
                data = message['data'].decode('utf-8')
                yield f"data: {data}\n\n"

    return Response(
        event_generator(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )