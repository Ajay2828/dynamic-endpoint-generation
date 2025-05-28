from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql
from typing import Dict, List

# Create main app
app = Flask(__name__)

DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'port': 5432,
    'host': 'localhost'
}

# Store endpoint configurations
endpoint_configs = {}

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

def insert_endpoint_to_db(endpoint_name, endpoint_path, query_str, created_by):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO endpoint_registry (endpoint_name, endpoint_path, query, created_by)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """, (endpoint_name, endpoint_path, query_str, created_by))
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

@app.route('/generate-endpoint', methods=['POST'])
def generate_endpoint():
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

    insert_endpoint_to_db(endpoint_name, endpoint_path, query_str, created_by)

    return jsonify({
        'message': f'Endpoint created at {endpoint_path}',
        'endpoint_path': endpoint_path,
        'method': 'GET'
    })


# Catch-all route for dynamic endpoints
@app.route('/dynamic/<path:endpoint_name>', methods=['GET'])
def handle_dynamic_endpoint(endpoint_name):
    if endpoint_name not in endpoint_configs:
        return jsonify({'error': f'Endpoint /{endpoint_name} not found'}), 404
    
    config = endpoint_configs[endpoint_name]
    filters = request.args.to_dict()
    
    
    
    return jsonify(result), status

@app.route('/list-endpoints', methods=['GET'])
def list_endpoints():
    return jsonify(endpoint_configs)

if __name__ == '__main__':
    app.run(debug=True)