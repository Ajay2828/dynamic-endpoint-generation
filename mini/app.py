from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import logging
from logging.handlers import RotatingFileHandler


# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configure extensions
    db.init_app(app)
    limiter.init_app(app)
    limiter.limit(app.config['RATE_LIMIT'])(app)
    
    # Database initialization
    with app.app_context():
        db.create_all()
    
    # Configure logging
    handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
