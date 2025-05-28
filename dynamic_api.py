from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql
from typing import Dict, List
from datetime import datetime,timedelta,timezone

# Create main app
app = Flask(__name__)

DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'port': 5432,
    'host': 'localhost'
}

def get_current_datetime():
    # Get the current local time
    local_now = datetime.now()
    # Define the IST offset (UTC+5:30)
    ist_offset = timedelta(hours=5, minutes=30)
    # Create the IST timezone
    ist_timezone = timezone(ist_offset)
    # Convert local time to IST
    ist_now = local_now.astimezone(ist_timezone)
    return ist_now.strftime('%Y-%m-%d %H:%M:%S')

def get_table_schema(schema_name: str, table_name: str) -> Dict[str, str]:
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = %s AND table_name = %s
        """, (schema_name, table_name))
    schema = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return schema

def make_dynamic_query(schema_name: str, table_name: str, select_columns: List[str], filter_columns: List[str]) -> str:
    """
    Returns a parameterized SQL query string with %s placeholders for filters.
    This function does NOT execute the query — just returns the query as a string.
    """
    select_clause = sql.SQL(', ').join(map(sql.Identifier, select_columns))

    base_query = sql.SQL("SELECT {} FROM {}.{}").format(
        select_clause,
        sql.Identifier(schema_name),
        sql.Identifier(table_name)
    )

    # Create WHERE clause with placeholders
    where_clauses = [
        sql.SQL("{} = %s").format(sql.Identifier(col)) for col in filter_columns
    ]

    if where_clauses:
        query = sql.SQL("{} WHERE {}").format(
            base_query,
            sql.SQL(" AND ").join(where_clauses)
        )
    else:
        query = base_query

    # Return the final query as a string (with %s placeholders)
    return query.as_string(psycopg2.connect(**DB_CONFIG))


def generate_endpoint_name(table_name: str, select_columns: List[str], filter_columns: List[str]) -> str:
    select_part = "_".join(select_columns)
    filter_part = "_".join(filter_columns) if filter_columns else "nofilter"
    endpoint_name = f"{table_name}__select_{select_part}__filter_{filter_part}"
    endpoint_name = endpoint_name.lower().replace(" ", "_")
    return endpoint_name

def insert_endpoint_to_db(endpoint_name, endpoint_path, query_str, created_by, created_at):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO endpoint_registry (endpoint_name, endpoint_path, query, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (endpoint_name, endpoint_path, query_str, created_by, created_at))
    endpoint_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return endpoint_id

def endpoint_exists(endpoint_name: str) -> bool:
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM endpoint_registry WHERE endpoint_name = %s LIMIT 1;",
        (endpoint_name,)
    )
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists

def get_query_by_endpoint_name(endpoint_name: str):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, query FROM endpoint_registry WHERE endpoint_name = %s
    """, (endpoint_name,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return {'id': result[0], 'query': result[1]}
    else:
        return None


def log_endpoint_usage(endpoint_id: int, accessed_at: str):
    """ Logs the usage of a dynamic endpoint in the database. """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO de_dynamic_api.endpoint_usage (endpoint_id, accessed_at)
        VALUES (%s, %s)
    """, (endpoint_id, accessed_at))
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/generate-endpoint', methods=['POST'])
def generate_endpoint():
    """ Generates a dynamic endpoint and a dynamic query will be stored in the database."""
    data = request.get_json()

    table_name = data.get('table_name')
    schema_name = data.get('schema_name', 'public')
    filter_columns = data.get('filter_columns', [])
    select_columns = data.get('select_columns', [])
    created_by = data.get('created_by', 'anonymous')

    if not table_name or not select_columns:
        return jsonify({'error': 'Both table_name and select_columns are required'}), 400

    schema = get_table_schema(schema_name, table_name)
    if not schema:
        return jsonify({'error': f'Table {table_name} not found'}), 404

    # Validate columns exist in table
    for col in select_columns + filter_columns:
        if col not in schema:
            return jsonify({'error': f'Column {col} not found in table {table_name}'}), 400

    endpoint_name = generate_endpoint_name(table_name, select_columns, filter_columns)
    endpoint_path = f'/dynamic/{endpoint_name}'

    if endpoint_exists(endpoint_name):
        return jsonify({'error': f'Endpoint already exists at {endpoint_path}'}), 400

    
    query_str = make_dynamic_query(schema_name, table_name, select_columns, filter_columns)
    created_at = get_current_datetime()
    insert_endpoint_to_db(endpoint_name, endpoint_path, query_str, created_by, created_at)

    return jsonify({
        'message': f'Endpoint created at {endpoint_path}',
        'endpoint_path': endpoint_path,
        'method': 'GET'
    })


# Catch-all route for dynamic endpoints
@app.route('/dynamic/<path:endpoint_name>', methods=['GET'])
def handle_dynamic_endpoint(endpoint_name):

    if not endpoint_exists(endpoint_name):
        return jsonify({'error': f'Endpoint /{endpoint_name} not found'}), 404
    
    filters = request.args.to_dict()

    filter_values = list(filters.values()) 
    result = get_query_by_endpoint_name(endpoint_name)
    query_template = result["query"]
    endpoint_id = result["id"]

    if not query_template:
        return jsonify({'error': 'No query found for this endpoint'}), 404
     
    final_query = sql.SQL(query_template)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(final_query, filter_values)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    log_endpoint_usage(endpoint_id, accessed_at=get_current_datetime())
    
    return jsonify([dict(zip(columns, rows))]), 200

if __name__ == '__main__':
    app.run(debug=True)