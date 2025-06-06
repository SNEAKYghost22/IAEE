from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import jwt
import requests
import datetime
import pymysql
from functools import wraps

pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key'

def handle_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            app.logger.error(f'Error in {func.__name__}: {str(e)}')
            return jsonify({
                'status': 'error',
                'message': str(e),
                'endpoint': request.endpoint
            }), 500
    return wrapper

def validate_json_request(required_fields=[]):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    'status': 'error',
                    'message': 'Content-Type must be application/json'
                }), 400

            data = request.get_json()
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No input data provided'
                }), 400

            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400

            return func(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/')
def index():
    return render_template('auth_service.html')

@app.route('/auth/login', methods=['POST'])
@handle_error
@validate_json_request(['username', 'password'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    # Fetch user by username
    response = requests.get(
        f'http://localhost:5001/users/by-username/{username}',
        timeout=5  # Add timeout for better error handling
    )

    if response.status_code == 404:
        return jsonify({
            'status': 'error',
            'message': 'User not found'
        }), 401

    if response.status_code != 200:
        return jsonify({
            'status': 'error',
            'message': 'Error during authentication'
        }), 500

    user = response.json()
    stored_password = user.get('password')

    if not stored_password or stored_password != password:
        return jsonify({
            'status': 'error',
            'message': 'Invalid password'
        }), 401

    # Generate token
    token = jwt.encode({
        'user_id': user['id'],
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'])

    return jsonify({
        'status': 'success',
        'message': 'Login successful',
        'data': {
            'token': token,
            'user_id': user['id'],
            'username': username
        }
    })

@app.route('/auth/verify', methods=['POST'])
@handle_error
def verify_token():
    # Cek token dari header Authorization
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({
            'status': 'error',
            'message': 'Token is missing in Authorization header'
        }), 401
    
    # Hapus 'Bearer ' jika ada
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
    else:
        token = auth_header

    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({
            'status': 'success',
            'data': {
                'valid': True,
                'user_id': data['user_id'],
                'username': data.get('username')
            }
        })
    except jwt.ExpiredSignatureError:
        return jsonify({
            'status': 'error',
            'message': 'Token has expired'
        }), 401
    except jwt.InvalidTokenError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid token'
        }), 401

if __name__ == '__main__':
    app.debug = True
    app.run(port=5002)
