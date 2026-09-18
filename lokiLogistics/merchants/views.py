from flask import Blueprint, request, jsonify
from lokiLogistics.extensions import db
from lokiLogistics.merchants.models import Merchant, Shop, ShopHistory
from lokiLogistics.merchants.forms import (
    MerchantSchema,
    MerchantDetailSchema,
    ShopSchema,
    ShopHistorySchema
)
from lokiLogistics.utils import publish_location_ping
from lokiLogistics.shipments.models import Shipment, ShipmentHistory
from lokiLogistics.jwt.tokens import token_required

merchants_bp = Blueprint('merchants', __name__, url_prefix='/api/merchants')

merchant_schema = MerchantSchema()
merchant_detail_schema = MerchantDetailSchema()
merchants_detail_schema = MerchantDetailSchema(many=True)

shop_schema = ShopSchema()
shops_schema = ShopSchema(many=True)
shop_history_schema = ShopHistorySchema(many=True)


# ==========================================
# MERCHANT CRUD ENDPOINTS
# ==========================================

@merchants_bp.route('', methods=['POST'])
@token_required(allowed_roles=['admin'])
def create_merchant(current_identity):
    data = request.get_json() or {}
    password = data.pop('password', None)
    
    merchant = merchant_schema.load(data)
    if password:
        merchant.set_password(password)

    db.session.add(merchant)
    db.session.commit()
    return merchant_detail_schema.dump(merchant), 201


@merchants_bp.route('', methods=['GET'])
@token_required(allowed_roles=['admin'])
def get_merchants(current_identity):
    merchants = Merchant.query.all()
    return jsonify(merchants_detail_schema.dump(merchants)), 200


@merchants_bp.route('/<int:id>', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin'])
def get_merchant(current_identity, id):
    if current_identity['role'] == 'merchant' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only view your own merchant account"}), 403

    merchant = Merchant.query.get_or_404(id)
    return merchant_detail_schema.dump(merchant), 200


@merchants_bp.route('/<int:id>', methods=['PUT', 'PATCH'])
@token_required(allowed_roles=['merchant', 'admin'])
def update_merchant(current_identity, id):
    if current_identity['role'] == 'merchant' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only update your own credentials"}), 403

    merchant = Merchant.query.get_or_404(id)
    data = request.get_json() or {}

    # Securely update password if supplied
    if 'password' in data:
        merchant.set_password(data.pop('password'))

    for key, value in data.items():
        if hasattr(merchant, key) and key not in ['id', 'created_at', 'password_hash']:
            setattr(merchant, key, value)

    db.session.commit()
    return merchant_detail_schema.dump(merchant), 200


@merchants_bp.route('/<int:id>', methods=['DELETE'])
@token_required(allowed_roles=['merchant', 'admin'])
def delete_merchant(current_identity, id):
    if current_identity['role'] == 'merchant' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only delete your own merchant account"}), 403

    merchant = Merchant.query.get_or_404(id)
    db.session.delete(merchant)
    db.session.commit()
    return jsonify({"message": f"Merchant {id} and associated shops deleted successfully"}), 200


# ==========================================
# SHOP CRUD & HISTORY ENDPOINTS
# ==========================================

@merchants_bp.route('/<int:merchant_id>/shops', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def create_shop(current_identity, merchant_id):
    if current_identity['role'] == 'merchant' and current_identity['id'] != merchant_id:
        return jsonify({"error": "Forbidden: Cannot create shops for another merchant"}), 403

    Merchant.query.get_or_404(merchant_id)
    data = request.get_json() or {}
    data['merchant_id'] = merchant_id
    
    shop = shop_schema.load(data)
    db.session.add(shop)
    db.session.commit()
    return shop_schema.dump(shop), 201


@merchants_bp.route('/<int:merchant_id>/shops', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin'])
def get_merchant_shops(current_identity, merchant_id):
    if current_identity['role'] == 'merchant' and current_identity['id'] != merchant_id:
        return jsonify({"error": "Forbidden: Cannot view shops belonging to another merchant"}), 403

    Merchant.query.get_or_404(merchant_id)
    shops = Shop.query.filter_by(merchant_id=merchant_id).all()
    return jsonify(shops_schema.dump(shops)), 200


@merchants_bp.route('/shops/<int:shop_id>', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin'])
def get_shop(current_identity, shop_id):
    shop = Shop.query.get_or_404(shop_id)

    if current_identity['role'] == 'merchant' and shop.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this shop"}), 403

    return shop_schema.dump(shop), 200


@merchants_bp.route('/shops/<int:shop_id>', methods=['PUT', 'PATCH'])
@token_required(allowed_roles=['merchant', 'admin'])
def update_shop(current_identity, shop_id):
    shop = Shop.query.get_or_404(shop_id)

    if current_identity['role'] == 'merchant' and shop.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this shop"}), 403

    data = request.get_json() or {}

    # Snapshot current state into ShopHistory before applying changes
    history_entry = ShopHistory(
        shop_id=shop.id,
        name=shop.name,
        address=shop.address,
        lat=shop.lat,
        lng=shop.lng
    )
    db.session.add(history_entry)

    # Update shop fields
    for key, value in data.items():
        if hasattr(shop, key) and key not in ['id', 'merchant_id', 'created_at']:
            setattr(shop, key, value)

    db.session.commit()
    return shop_schema.dump(shop), 200


@merchants_bp.route('/shops/<int:shop_id>', methods=['DELETE'])
@token_required(allowed_roles=['merchant', 'admin'])
def delete_shop(current_identity, shop_id):
    shop = Shop.query.get_or_404(shop_id)

    if current_identity['role'] == 'merchant' and shop.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this shop"}), 403

    db.session.delete(shop)
    db.session.commit()
    return jsonify({"message": f"Shop {shop_id} deleted successfully"}), 200


@merchants_bp.route('/shops/<int:shop_id>/history', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin'])
def get_shop_history(current_identity, shop_id):
    shop = Shop.query.get_or_404(shop_id)

    if current_identity['role'] == 'merchant' and shop.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this shop"}), 403

    history = ShopHistory.query.filter_by(shop_id=shop_id).order_by(ShopHistory.changed_at.desc()).all()
    return jsonify(shop_history_schema.dump(history)), 200


@merchants_bp.route('/shipments/<int:shipment_id>/override-pickup', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def override_pickup(current_identity, shipment_id):
    shipment = Shipment.query.get_or_404(shipment_id)

    # Verify merchant ownership of the shipment
    if current_identity['role'] == 'merchant' and shipment.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Shipment belongs to another merchant"}), 403

    data = request.get_json() or {}
    reason = data.get('reason', '').strip()

    if not reason:
        return jsonify({
            "error": "A valid reason is required for manual pickup override."
        }), 400

    if shipment.status in ['PICKED_UP', 'IN_TRANSIT']:
        return jsonify({
            "message": "Shipment has already been picked up."
        }), 200

    if shipment.status in ['DELIVERED', 'CANCELLED']:
        return jsonify({
            "error": f"Cannot override pickup for shipment in '{shipment.status}' status."
        }), 400

    previous_status = shipment.status
    shipment.status = 'PICKED_UP'
    shipment.pickup_attempts = 0

    history_entry = ShipmentHistory(
        shipment_id=shipment.id,
        status='PICKED_UP',
        lat=shipment.pickup_lat,
        lng=shipment.pickup_lng,
        notes=f"MANUAL OVERRIDE BY MERCHANT ID {current_identity['id']}: {reason} (Previous Status: {previous_status})"
    )
    db.session.add(history_entry)
    db.session.commit()

    publish_location_ping(
        shipment_id=shipment.id,
        lat=shipment.pickup_lat,
        lng=shipment.pickup_lng,
        status='PICKED_UP'
    )

    return jsonify({
        "message": "Shipment pickup manually approved successfully.",
        "shipment_id": shipment.id,
        "status": shipment.status,
        "override_reason": reason
    }), 200