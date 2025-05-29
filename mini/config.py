import os
from dotenv import load_dotenv


load_dotenv()

DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'port': 5432,
    'host': 'localhost'
}

class Config:
    # PostgreSQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'dynamic_api')
    DB_USER = os.getenv('DB_USER')
    DB_PASS = os.getenv('DB_PASS')
    
    # JWT
    API_KEY = os.getenv('API_KEY', 'super-secret-change-me')
    
    # Rate Limiting
    RATE_LIMIT = os.getenv('RATE_LIMIT', '5/minute')