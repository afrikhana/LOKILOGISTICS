import jwt
import time
import inspect
from functools import wraps
from flask import request, jsonify, current_app, g

VALID_ROLES = {"merchant", "customer", "rider", "admin"}

def generate_access_token(entity_id: int, role: str) -> str:
    """
    Generates a JWT token containing the entity ID and role.
    role can be: 'merchant', 'customer', 'rider', or 'admin'
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    now = int(time.time())
    payload = {
        "sub": str(entity_id),
        "role": role,
        "iat": now,
        "exp": now + (8 * 3600)
    }
    
    token = jwt.encode(payload, str(current_app.config["SECRET_KEY"]), algorithm="HS256")
    
    if isinstance(token, bytes):
        token = token.decode("utf-8")
        
    return token

def token_required(allowed_roles=None):
    """
    Decorator to protect routes and inject the authenticated identity into kwargs
    if expected, or fall back to flask.g.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            if "Authorization" in request.headers:
                auth_header = request.headers["Authorization"].strip()
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    token = parts[1]
                elif len(parts) == 1:
                    token = parts[0]

            if not token:
                return jsonify({"error": "Authorization token is missing"}), 401

            try:
                data = jwt.decode(
                    token, 
                    str(current_app.config["SECRET_KEY"]), 
                    algorithms=["HS256"],
                    leeway=10
                )
                
                current_identity = {
                    "id": int(data["sub"]),
                    "sub": str(data["sub"]),
                    "role": data["role"]
                }
                
                if allowed_roles:
                    if isinstance(allowed_roles, str) and data["role"] != allowed_roles:
                        return jsonify({"error": f"Forbidden: Requires '{allowed_roles}' role"}), 403
                    elif isinstance(allowed_roles, (list, tuple, set)) and data["role"] not in allowed_roles:
                        return jsonify({"error": f"Forbidden: Requires one of {list(allowed_roles)} roles"}), 403

                g.current_user = current_identity

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token has expired"}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({"error": f"Invalid token: {str(e)}"}), 401

            sig = inspect.signature(f)
            if 'current_identity' in sig.parameters:
                kwargs['current_identity'] = current_identity

            return f(*args, **kwargs)
        return decorated
    return decorator