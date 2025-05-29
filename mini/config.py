import os
from dotenv import load_dotenv


load_dotenv()


class Config:
    # PostgreSQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'dynamic_api')
    DB_USER = os.getenv('DB_USER')
    DB_PASS = os.getenv('DB_PASS')
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'super-secret-change-me')
    JWT_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE', '60'))
    
    # Rate Limiting
    RATE_LIMIT = os.getenv('RATE_LIMIT', '100/hour')