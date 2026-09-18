# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import json
from flask import flash, current_app
from lokiLogistics.extensions import redis_client


def flash_errors(form, category="warning"):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text} - {error}", category)


def publish_location_ping(shipment_id, lat, lng, status="IN_TRANSIT"):
    """
    Updates Redis RAM cache and publishes real-time location pings 
    to the SSE stream channel for active shipments.
    """
    # 1. Update Redis RAM Cache (24-hour TTL)
    live_key = f"shipment:{shipment_id}:live"
    redis_client.hset(live_key, mapping={"lat": lat, "lng": lng})
    redis_client.expire(live_key, 86400)

    # 2. Publish payload to Redis Pub/Sub channel
    payload = json.dumps({
        "shipment_id": shipment_id,
        "lat": lat,
        "lng": lng,
        "status": status
    })
    redis_client.publish(f"shipment:{shipment_id}:stream", payload)