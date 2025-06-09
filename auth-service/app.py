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
# PENTING: PASTIKAN SECRET_KEY INI SAMA DI SEMUA SERVICE (payment, reward)
app.config['SECRET_KEY'] = 'super-secret-key-bankin-app' 

# Decorator untuk penanganan error umum
def handle_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Menggunakan app.logger.error untuk logging standar Flask
            app.logger.error(f'AUTH_SERVICE: Exception in {func.__name__}: {str(e)}')
            return jsonify({
                'status': 'error',
                'message': f'Internal Server Error: {str(e)}',
                'endpoint': request.endpoint
            }), 500
    return wrapper

# Decorator untuk validasi input JSON
def validate_json_request(required_fields=[]):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                print(f"AUTH_SERVICE: Error - Content-Type must be application/json for {request.endpoint}.")
                return jsonify({
                    'status': 'error',
                    'message': 'Content-Type must be application/json'
                }), 400

            data = request.get_json(silent=True) # silent=True agar tidak error jika body kosong
            if data is None: # Jika Content-Type: application/json tapi body kosong
                print(f"AUTH_SERVICE: Error - Empty JSON body provided for {request.endpoint}.")
                return jsonify({
                    'status': 'error',
                    'message': 'Empty JSON body provided'
                }), 400
            
            # Validasi field yang wajib ada
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"AUTH_SERVICE: Error - Missing required fields: {', '.join(missing_fields)} for {request.endpoint}. Data: {data}")
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400

            return func(*args, **kwargs)
        return wrapper
    return decorator

# Route untuk halaman utama (frontend)
@app.route('/')
def index_auth():
    return render_template('auth_service.html')

# Route untuk proses login
@app.route('/auth/login', methods=['POST'])
@handle_error
@validate_json_request(['username', 'password'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    try:
        # Fetch user by username from User Service with timeout
        response = requests.get(
            f'http://localhost:5001/users/by-username/{username}',
            timeout=5
        )

        if response.status_code == 404:
            print(f"AUTH_SERVICE: Login failed - User '{username}' not found.")
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 401

        if not response.ok: # Tangkap status non-200/404 lainnya
            print(f"AUTH_SERVICE: Error fetching user from User Service. Status: {response.status_code}, Response: {response.text}")
            return jsonify({
                'status': 'error',
                'message': 'Error during authentication: User Service issue'
            }), 500

        user = response.json()
        stored_password = user.get('password')

        if not stored_password or stored_password != password: # PERINGATAN: Dalam produksi, gunakan hashing password!
            print(f"AUTH_SERVICE: Login failed for '{username}' - Invalid password.")
            return jsonify({
                'status': 'error',
                'message': 'Invalid password'
            }), 401

        # Generate token JWT
        token = jwt.encode({
            'user_id': user['id'],
            'username': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Token kadaluarsa dalam 24 jam
        }, app.config['SECRET_KEY'], algorithm='HS256') # Pastikan algorithm terdefinisi

        print(f"AUTH_SERVICE: Login successful for user '{username}' (ID: {user['id']}).")
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'token': token,
                'user_id': user['id'],
                'username': username
            }
        })
    except requests.exceptions.RequestException as e:
        print(f"AUTH_SERVICE: Error - Failed to connect to User Service during login: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to connect to User Service for authentication'
        }), 500


# Route untuk verifikasi token JWT
@app.route('/auth/verify', methods=['POST'])
@handle_error
def verify_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        print("AUTH_SERVICE: Error - Token is missing in Authorization header.")
        return jsonify({
            'status': 'error',
            'message': 'Token is missing in Authorization header'
        }), 401
    
    # Ekstrak token dari header (hapus 'Bearer ' jika ada)
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
    else:
        token = auth_header # Jika tidak ada 'Bearer ', asumsikan seluruh header adalah token

    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        print(f"AUTH_SERVICE: Success - Token verified for user ID: {data['user_id']}.")
        return jsonify({
            'status': 'success',
            'data': {
                'valid': True,
                'user_id': data['user_id'],
                'username': data.get('username')
            }
        })
    except jwt.ExpiredSignatureError:
        print("AUTH_SERVICE: Error - Token verification failed: Token has expired.")
        return jsonify({
            'status': 'error',
            'message': 'Token has expired'
        }), 401
    except jwt.InvalidTokenError:
        print("AUTH_SERVICE: Error - Token verification failed: Invalid token.")
        return jsonify({
            'status': 'error',
            'message': 'Invalid token'
        }), 401
    except Exception as e:
        print(f"AUTH_SERVICE: Exception - Unexpected error during token verification: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'An unexpected error occurred during token verification: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.debug = True # Aktifkan debug mode untuk melihat log di konsol
    print("AUTH_SERVICE: Starting on port 5002...")
    app.run(port=5002)