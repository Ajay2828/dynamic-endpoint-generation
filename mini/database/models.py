from datetime import datetime
from app import db


class ApiEndpoint(db.Model):
    __tablename__ = 'api_endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint_name = db.Column(db.String(120), unique=True, nullable=False)
    table_name = db.Column(db.String(120), nullable=False)
    source_columns = db.Column(db.JSON, nullable=False)
    filter_columns = db.Column(db.JSON, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    creator = db.relationship('User', backref='endpoints')


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    scopes = db.Column(db.JSON, default=['query:data'])
    is_active = db.Column(db.Boolean, default=True)