from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import requests
import pymysql
import datetime 

pymysql.install_as_MySQLdb()

app = Flask(__name__)
# Konfigurasi CORS
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Accept"], "expose_headers": ["Authorization"]}})

# Konfigurasi Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/iae_transaction_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Model Database untuk Transaksi
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'withdrawal' or 'deposit'
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    description = db.Column(db.String(255), nullable=True) 

# Route untuk halaman utama (frontend)
@app.route('/')
def index_transaction():
    return render_template('transaction_service.html')

# Route untuk membuat transaksi baru
@app.route('/transactions', methods=['POST'])
def create_transaction():
    data = request.get_json()
    token = request.headers.get('Authorization')
    
    if not token:
        print("TRANSACTION_SERVICE: Error - Token is missing for create_transaction.")
        return jsonify({'message': 'Token is missing'}), 401
    
    # Validasi input data dasar dari request body
    required_fields = ['user_id', 'amount', 'type']
    if not all(field in data for field in required_fields):
        print(f"TRANSACTION_SERVICE: Error - Missing required fields: {data}")
        return jsonify({'message': f'Missing required fields: {", ".join(required_fields)}'}), 400

    user_id = data.get('user_id')
    amount = data.get('amount')
    transaction_type = data.get('type')

    # Validasi tipe data dan nilai input
    if not isinstance(user_id, int) or user_id <= 0:
        print(f"TRANSACTION_SERVICE: Error - Invalid user_id: {user_id}. Must be a positive integer.")
        return jsonify({'message': 'Invalid user_id provided. Must be a positive integer.'}), 400
    if not isinstance(amount, (int, float)) or amount <= 0:
        print(f"TRANSACTION_SERVICE: Error - Invalid amount: {amount}. Must be a positive number.")
        return jsonify({'message': 'Invalid amount provided. Must be a positive number.'}), 400
    if transaction_type not in ['withdrawal', 'deposit']:
        print(f"TRANSACTION_SERVICE: Error - Invalid transaction_type: {transaction_type}. Must be 'withdrawal' or 'deposit'.")
        return jsonify({'message': 'Invalid transaction type. Must be "withdrawal" or "deposit".'}), 400

    # Verifikasi token dengan Auth Service
    try:
        print(f"TRANSACTION_SERVICE: Attempting token verification with Auth Service for user {user_id}...")
        auth_response = requests.post(
            'http://localhost:5002/auth/verify', 
            headers={'Authorization': token},
            json={}, # Body kosong untuk memastikan Content-Type: application/json
            timeout=5 # Timeout untuk mencegah layanan menggantung
        )
        auth_data = auth_response.json()
        if not auth_response.ok or not auth_data.get('status') == 'success' or not auth_data.get('data', {}).get('valid'):
            print(f"TRANSACTION_SERVICE: Error - Token verification failed. Status: {auth_response.status_code}, Response: {auth_response.text}")
            return jsonify({'message': 'Unauthorized or invalid token', 'details': auth_data.get('message')}), 401
        print("TRANSACTION_SERVICE: Success - Token verified successfully.")
    except requests.exceptions.ConnectionError as e: # Tangani khusus ConnectionError
        print(f"TRANSACTION_SERVICE: Error - Connection to Auth Service failed: {e}")
        return jsonify({'message': 'Failed to connect to authentication service'}), 500
    except requests.exceptions.RequestException as e: # Tangani RequestException lainnya
        print(f"TRANSACTION_SERVICE: Error - Request to Auth Service failed: {e}")
        return jsonify({'message': 'Authentication service request failed'}), 500
    except Exception as e:
        print(f"TRANSACTION_SERVICE: Exception - Unexpected error during token verification: {str(e)}")
        return jsonify({'message': f'Internal server error during auth verification: {str(e)}'}), 500
    
    # Ambil saldo user dari User Service
    try:
        print(f"TRANSACTION_SERVICE: Fetching user {user_id} balance from User Service...")
        user_response = requests.get(f'http://localhost:5001/users/{user_id}', timeout=5) 
        if user_response.status_code == 404:
            print(f"TRANSACTION_SERVICE: Error - User ID: {user_id} not found in User Service.")
            return jsonify({'message': 'User not found'}), 404
        if not user_response.ok:
            print(f"TRANSACTION_SERVICE: Error - Failed to fetch user data for {user_id}. Status: {user_response.status_code}, Response: {user_response.text}")
            return jsonify({'message': 'Failed to fetch user data from User Service'}), 500
        user = user_response.json()
        current_balance = user.get('balance', 0.0)
        print(f"TRANSACTION_SERVICE: User {user_id} current balance: {current_balance}.")
    except requests.exceptions.ConnectionError as e:
        print(f"TRANSACTION_SERVICE: Error - Connection to User Service failed (fetch balance): {e}")
        return jsonify({'message': 'Failed to connect to user service (fetch balance)'}), 500
    except requests.exceptions.RequestException as e:
        print(f"TRANSACTION_SERVICE: Error - Request to User Service failed (fetch balance): {e}")
        return jsonify({'message': 'User service request failed (fetch balance)'}), 500
    except Exception as e:
        print(f"TRANSACTION_SERVICE: Exception - Unexpected error fetching user data: {str(e)}")
        return jsonify({'message': f'Internal server error fetching user data: {str(e)}'}), 500
    
    # Jika penarikan, pastikan saldo mencukupi
    if transaction_type == 'withdrawal':
        if current_balance < amount: # Menggunakan '<' untuk memastikan saldo CUKUP untuk penarikan
            print(f"TRANSACTION_SERVICE: Error - Insufficient balance for user {user_id}. Current: {current_balance}, Attempted withdrawal: {amount}.")
            return jsonify({'message': 'Insufficient balance'}), 400
        new_balance = current_balance - amount  # Saldo berkurang
    elif transaction_type == 'deposit':
        new_balance = current_balance + amount  # Saldo bertambah
    else:
        # Ini seharusnya sudah divalidasi di atas, tapi sebagai fallback
        print(f"TRANSACTION_SERVICE: Error - Invalid transaction_type encountered: {transaction_type}.")
        return jsonify({'message': 'Invalid transaction type'}), 400
    
    # Update saldo di User Service
    try:
        print(f"TRANSACTION_SERVICE: Updating user {user_id} balance to {new_balance} in User Service...")
        update_response = requests.put(
            f'http://localhost:5001/users/{user_id}', 
            json={'balance': new_balance},
            timeout=5 
        )
        if not update_response.ok:
            print(f"TRANSACTION_SERVICE: Error - Failed to update user {user_id} balance. Status: {update_response.status_code}, Response: {update_response.text}")
            return jsonify({'message': 'Failed to update user balance in User Service'}), 500
        print(f"TRANSACTION_SERVICE: Success - User {user_id} balance updated successfully to {new_balance}.")
    except requests.exceptions.ConnectionError as e:
        print(f"TRANSACTION_SERVICE: Error - Connection to User Service failed (update balance): {e}")
        return jsonify({'message': 'Failed to update user balance (User Service connection error)'}), 500
    except requests.exceptions.RequestException as e:
        print(f"TRANSACTION_SERVICE: Error - Request to User Service failed (update balance): {e}")
        return jsonify({'message': 'User service request failed (update balance)'}), 500
    except Exception as e:
        print(f"TRANSACTION_SERVICE: Exception - Unexpected error updating user balance: {str(e)}")
        return jsonify({'message': f'Internal server error updating user balance: {str(e)}'}), 500
    
    # Tambahkan transaksi ke database lokal
    try:
        new_transaction = Transaction(
            user_id=user_id, 
            amount=amount, 
            type=transaction_type,
            description=data.get('description') 
        )
        db.session.add(new_transaction)
        db.session.commit()
        print(f"TRANSACTION_SERVICE: Success - Transaction {new_transaction.id} created successfully for user {user_id}. New balance: {new_balance}.")
        
    except Exception as e:
        db.session.rollback() # Rollback jika ada error saat menyimpan transaksi
        print(f"TRANSACTION_SERVICE: Exception - Error saving transaction to database: {str(e)}.")
        # PERINGATAN: Jika transaksi gagal disimpan di sini, saldo user sudah terupdate.
        # Dalam sistem produksi, Anda perlu strategi kompensasi untuk mengembalikan saldo.
        return jsonify({'message': f'Error saving transaction to database: {str(e)}'}), 500
        
    # Kembalikan respons sukses
    return jsonify({
        'message': 'Transaction created successfully',
        'transaction_id': new_transaction.id,
        'new_balance': new_balance
    }), 201

# Route untuk mendapatkan riwayat transaksi user
@app.route('/transactions/user/<int:user_id>', methods=['GET'])
def get_user_transactions(user_id):
    token = request.headers.get('Authorization')
    if not token:
        print("TRANSACTION_SERVICE: Error - Token is missing for get_user_transactions.")
        return jsonify({'message': 'Token is missing'}), 401
        
    try:
        print(f"TRANSACTION_SERVICE: Attempting token verification for user {user_id} (get_user_transactions)...")
        auth_response = requests.post(
            'http://localhost:5002/auth/verify', 
            headers={'Authorization': token},
            json={}, 
            timeout=5
        )
        if not auth_response.ok:
            print(f"TRANSACTION_SERVICE: Error - Token verification failed for get_user_transactions. Status: {auth_response.status_code}, Response: {auth_response.text}")
            return jsonify({'message': 'Failed to verify token'}), 401

        auth_data = auth_response.json()
        if not auth_data.get('status') == 'success' or not auth_data.get('data', {}).get('valid'):
            print(f"TRANSACTION_SERVICE: Error - Invalid token for get_user_transactions. Details: {auth_data.get('message')}")
            return jsonify({'message': 'Invalid token'}), 401
        print("TRANSACTION_SERVICE: Success - Token verified successfully for get_user_transactions.")

        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.timestamp.desc()).all()
        print(f"TRANSACTION_SERVICE: Fetched {len(transactions)} transactions for user {user_id}.")
        return jsonify([{
            'id': t.id,
            'amount': t.amount,
            'type': t.type,
            'timestamp': t.timestamp.isoformat(),
            'description': t.description 
        } for t in transactions])
        
    except requests.exceptions.ConnectionError as e:
        print(f"TRANSACTION_SERVICE: Error - Connection to Auth Service failed (get_user_transactions): {e}")
        return jsonify({'message': 'Failed to connect to auth service'}), 500
    except requests.exceptions.RequestException as e:
        print(f"TRANSACTION_SERVICE: Error - Request to Auth Service failed (get_user_transactions): {e}")
        return jsonify({'message': 'Authentication service request failed'}), 500
    except Exception as e:
        print(f"TRANSACTION_SERVICE: Exception - General Error getting user transactions: {str(e)}")
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        # WARNING: db.drop_all() akan MENGHAPUS SEMUA DATA!
        # Gunakan hanya dalam pengembangan atau jika Anda yakin ingin menghapus data.
        # db.drop_all() 
        db.create_all() # Membuat tabel jika belum ada
    print("TRANSACTION_SERVICE: Starting on port 5003...")
    app.run(port=5003, debug=True)