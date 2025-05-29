import os
import threading
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql
import openai
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Configure cache
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
AI_MODEL = "gpt-4"  # or "gpt-3.5-turbo" for cost savings

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'mydatabase'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASS', 'postgres')
}

# Thread-safe storage for endpoints
endpoint_registry = {}
registry_lock = threading.Lock()

def get_db_connection():
    """Create and return a new database connection"""
    return psycopg2.connect(**DB_CONFIG)

def generate_ai_insights(query: str, data: list, analysis_type: str = "standard"):
    """
    Generate AI analysis based on query and results
    """
    prompts = {
        "standard": f"""
        Analyze this database query and results:
        Query: {query}
        Data Sample: {data[:3]} (showing first 3 of {len(data)} records)
        
        Provide:
        1. Key statistical insights
        2. Notable patterns/trends
        3. Data quality observations
        4. 3 actionable recommendations
        """,
        "technical": f"""
        Analyze this SQL query execution:
        Query: {query}
        Returned {len(data)} records
        
        Provide:
        1. Query optimization suggestions
        2. Index recommendations
        3. Schema improvement ideas
        4. Potential performance bottlenecks
        """,
        "business": f"""
        Analyze these business records:
        Query: {query}
        Data Sample: {data[:5]}
        
        Provide:
        1. Key business insights
        2. Revenue/profit opportunities
        3. Risk factors
        4. Strategic recommendations
        """
    }
    
    try:
        response = openai.ChatCompletion.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a data analysis assistant"},
                {"role": "user", "content": prompts.get(analysis_type, prompts["standard"])}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI analysis failed: {str(e)}"

@app.route('/api/endpoints', methods=['GET'])
@limiter.limit("10/minute")
def list_endpoints():
    """List all registered endpoints"""
    with registry_lock:
        return jsonify({
            "endpoints": list(endpoint_registry.keys()),
            "count": len(endpoint_registry)
        })

@app.route('/api/create', methods=['POST'])
@limiter.limit("5/minute")
def create_endpoint():
    """
    Create a new dynamic endpoint
    Expects JSON:
    {
        "endpoint_name": "sales-data",
        "table_name": "sales",
        "columns": ["date", "product", "amount"],
        "filter_fields": ["region", "quarter"],
        "description": "Sales data by product"
    }
    """
    required_fields = ['endpoint_name', 'table_name', 'columns']
    data = request.json
    
    # Validate input
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Create the handler function
    def query_handler():
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Build base query
            base_query = sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(',').join(map(sql.Identifier, data['columns'])),
                sql.Identifier(data['table_name'])
            )
            
            # Add filters from query parameters
            filters = {}
            where_clauses = []
            params = []
            
            if 'filter_fields' in data:
                for field in data['filter_fields']:
                    if field in request.args:
                        filters[field] = request.args[field]
                        where_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(field)))
                        params.append(request.args[field])
            
            # Finalize query
            if where_clauses:
                final_query = sql.SQL("{} WHERE {}").format(
                    base_query,
                    sql.SQL(" AND ").join(where_clauses)
                )
            else:
                final_query = base_query
            
            # Execute query
            cur.execute(final_query, params)
            
            # Get results
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            # AI Analysis if requested
            ai_analysis = None
            if request.args.get('ai_analyze', '').lower() in ('true', '1', 'yes'):
                analysis_type = request.args.get('analysis_type', 'standard')
                ai_analysis = generate_ai_insights(
                    final_query.as_string(conn),
                    results,
                    analysis_type
                )
            
            response = {
                "metadata": {
                    "endpoint": data['endpoint_name'],
                    "table": data['table_name'],
                    "query": final_query.as_string(conn),
                    "record_count": len(results)
                },
                "data": results
            }
            
            if ai_analysis:
                response["ai_analysis"] = ai_analysis
            
            return jsonify(response)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            cur.close()
            conn.close()
    
    # Store the endpoint configuration
    with registry_lock:
        endpoint_registry[data['endpoint_name']] = {
            "handler": query_handler,
            "config": data
        }
    
    return jsonify({
        "status": "success",
        "endpoint": f"/query/{data['endpoint_name']}",
        "ai_capabilities": {
            "available": True,
            "usage": "Add ?ai_analyze=true to request",
            "analysis_types": ["standard", "technical", "business"]
        }
    }), 201

@app.route('/query/<endpoint_name>', methods=['GET'])
@limiter.limit("60/minute")
@cache.cached(timeout=300, query_string=True)
def handle_query(endpoint_name):
    """Main query handler for dynamic endpoints"""
    with registry_lock:
        if endpoint_name not in endpoint_registry:
            return jsonify({"error": "Endpoint not found"}), 404
        
        handler = endpoint_registry[endpoint_name]['handler']
    
    return handler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
