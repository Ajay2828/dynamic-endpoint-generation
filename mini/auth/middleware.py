from functools import wraps
from flask import current_app
from flask import request, jsonify


def api_key_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != current_app.config.get('API_KEY'):
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper
