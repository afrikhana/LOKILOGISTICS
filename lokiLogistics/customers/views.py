from flask import Blueprint, request, jsonify
from lokiLogistics.extensions import db
from lokiLogistics.customers.models import Customer, CustomerAddress, CustomerAddressHistory
from lokiLogistics.customers.forms import (
    CustomerSchema,
    CustomerDetailSchema,
    CustomerAddressSchema,
    CustomerAddressHistorySchema
)
from lokiLogistics.jwt.tokens import token_required

customers_bp = Blueprint('customers', __name__, url_prefix='/api/customers')

customer_schema = CustomerSchema()
customer_detail_schema = CustomerDetailSchema()
customers_detail_schema = CustomerDetailSchema(many=True)

address_schema = CustomerAddressSchema()
addresses_schema = CustomerAddressSchema(many=True)
address_history_schema = CustomerAddressHistorySchema(many=True)

# ==========================================
# CUSTOMER CRUD ENDPOINTS
# ==========================================

@customers_bp.route('', methods=['POST'])
@token_required(allowed_roles=['merchant', 'admin'])
def create_customer(current_identity):
    data = request.get_json() or {}
    
    # Link customer to merchant if created by a merchant
    if current_identity['role'] == 'merchant':
        data['merchant_id'] = current_identity['id']

    # Extract raw password for hashing
    password = data.pop('password', None)
    customer = customer_schema.load(data)
    
    if password:
        customer.set_password(password)

    db.session.add(customer)
    db.session.commit()
    return customer_detail_schema.dump(customer), 201


@customers_bp.route('', methods=['GET'])
@token_required(allowed_roles=['merchant', 'admin'])
def get_customers(current_identity):
    if current_identity['role'] == 'merchant':
        customers = Customer.query.filter_by(merchant_id=current_identity['id']).all()
    else:
        customers = Customer.query.all()
        
    return jsonify(customers_detail_schema.dump(customers)), 200


@customers_bp.route('/<int:id>', methods=['GET'])
@token_required(allowed_roles=['merchant', 'customer', 'admin'])
def get_customer(current_identity, id):
    customer = Customer.query.get_or_404(id)

    # Access control: Customers can view themselves; Merchants can view their registered customers
    if current_identity['role'] == 'customer' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only access your own profile"}), 403

    if current_identity['role'] == 'merchant' and customer.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Customer is not associated with your merchant account"}), 403

    return customer_detail_schema.dump(customer), 200


@customers_bp.route('/<int:id>', methods=['PUT', 'PATCH'])
@token_required(allowed_roles=['customer', 'admin'])
def update_customer(current_identity, id):
    if current_identity['role'] == 'customer' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only update your own profile"}), 403

    customer = Customer.query.get_or_404(id)
    data = request.get_json() or {}

    # Handle password updates securely
    if 'password' in data:
        customer.set_password(data.pop('password'))

    # Prevent modification of immutable fields
    for key, value in data.items():
        if hasattr(customer, key) and key not in ['id', 'created_at', 'password_hash', 'merchant_id']:
            setattr(customer, key, value)

    db.session.commit()
    return customer_detail_schema.dump(customer), 200


@customers_bp.route('/<int:id>', methods=['DELETE'])
@token_required(allowed_roles=['customer', 'admin'])
def delete_customer(current_identity, id):
    if current_identity['role'] == 'customer' and current_identity['id'] != id:
        return jsonify({"error": "Forbidden: You can only delete your own profile"}), 403

    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    return jsonify({"message": f"Customer {id} deleted successfully"}), 200


# ==========================================
# CUSTOMER ADDRESS & HISTORY ENDPOINTS
# ==========================================

@customers_bp.route('/<int:customer_id>/addresses', methods=['POST'])
@token_required(allowed_roles=['customer', 'admin'])
def add_customer_address(current_identity, customer_id):
    if current_identity['role'] == 'customer' and current_identity['id'] != customer_id:
        return jsonify({"error": "Forbidden: You cannot add addresses to another account"}), 403

    Customer.query.get_or_404(customer_id)
    data = request.get_json() or {}
    data['customer_id'] = customer_id

    address = address_schema.load(data)
    db.session.add(address)
    db.session.commit()
    return address_schema.dump(address), 201


@customers_bp.route('/<int:customer_id>/addresses', methods=['GET'])
@token_required(allowed_roles=['merchant', 'customer', 'admin'])
def get_customer_addresses(current_identity, customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if current_identity['role'] == 'customer' and current_identity['id'] != customer_id:
        return jsonify({"error": "Forbidden: You cannot access addresses for another account"}), 403

    if current_identity['role'] == 'merchant' and customer.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Customer is not associated with your account"}), 403

    addresses = CustomerAddress.query.filter_by(customer_id=customer_id).all()
    return jsonify(addresses_schema.dump(addresses)), 200


@customers_bp.route('/addresses/<int:address_id>', methods=['PUT', 'PATCH'])
@token_required(allowed_roles=['customer', 'admin'])
def update_customer_address(current_identity, address_id):
    address = CustomerAddress.query.get_or_404(address_id)

    if current_identity['role'] == 'customer' and address.customer_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this address"}), 403

    data = request.get_json() or {}

    # Snapshot existing state into history before applying updates
    history_entry = CustomerAddressHistory(
        address_id=address.id,
        label=address.label,
        address=address.address,
        lat=address.lat,
        lng=address.lng
    )
    db.session.add(history_entry)

    for key, value in data.items():
        if hasattr(address, key) and key not in ['id', 'customer_id', 'created_at']:
            setattr(address, key, value)

    db.session.commit()
    return address_schema.dump(address), 200


@customers_bp.route('/addresses/<int:address_id>', methods=['DELETE'])
@token_required(allowed_roles=['customer', 'admin'])
def delete_customer_address(current_identity, address_id):
    address = CustomerAddress.query.get_or_404(address_id)

    if current_identity['role'] == 'customer' and address.customer_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this address"}), 403

    db.session.delete(address)
    db.session.commit()
    return jsonify({"message": f"Address {address_id} deleted successfully"}), 200


@customers_bp.route('/addresses/<int:address_id>/history', methods=['GET'])
@token_required(allowed_roles=['merchant', 'customer', 'admin'])
def get_address_history(current_identity, address_id):
    address = CustomerAddress.query.get_or_404(address_id)
    customer = Customer.query.get(address.customer_id)

    if current_identity['role'] == 'customer' and address.customer_id != current_identity['id']:
        return jsonify({"error": "Forbidden: You do not own this address"}), 403

    if current_identity['role'] == 'merchant' and customer and customer.merchant_id != current_identity['id']:
        return jsonify({"error": "Forbidden: Address belongs to a customer outside your account"}), 403

    history = CustomerAddressHistory.query.filter_by(address_id=address_id).order_by(CustomerAddressHistory.changed_at.desc()).all()
    return jsonify(address_history_schema.dump(history)), 200