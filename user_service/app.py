from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pymysql

pymysql.install_as_MySQLdb()

app = Flask(__name__)

# Konfigurasi CORS: Izinkan semua origin, metode, dan header untuk kemudahan pengembangan
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Accept"], "expose_headers": ["Authorization"]}})

# Konfigurasi Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/iae_user_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Model Database untuk User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # PERINGATAN: Dalam produksi, gunakan hashing password!
    balance = db.Column(db.Float, default=0.0)

# Route untuk halaman utama (frontend)
@app.route('/')
def index_user():
    return render_template('user_service.html')

# Route untuk membuat user baru
@app.route('/users', methods=['POST', 'OPTIONS'])
def create_user():
    # Tangani preflight request untuk CORS
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        if not data:
            print("USER_SERVICE: Error - No input data provided for create_user.")
            return jsonify({'message': 'No input data provided'}), 400
        
        # Validasi field yang wajib ada
        if 'username' not in data or 'password' not in data:
            print(f"USER_SERVICE: Error - Missing required fields (username, password) in data: {data}")
            return jsonify({'message': 'Missing required fields (username, password)'}), 400

        # Cek apakah username sudah ada
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            print(f"USER_SERVICE: Conflict - Username '{data['username']}' already exists.")
            return jsonify({'message': 'Username already exists'}), 409

        # Buat objek User baru
        new_user = User(
            username=data['username'],
            password=data['password'],
            balance=data.get('balance', 0.0) # Set default balance jika tidak ada
        )
        db.session.add(new_user)
        db.session.commit()
        print(f"USER_SERVICE: Success - User '{new_user.username}' created with ID: {new_user.id} and Balance: {new_user.balance}.")
        
        return jsonify({
            'message': 'User created successfully',
            'user_id': new_user.id,
            'username': new_user.username,
            'balance': new_user.balance
        }), 201
    except Exception as e:
        db.session.rollback() # Rollback transaksi jika ada error
        print(f"USER_SERVICE: Exception - Error creating user: {str(e)}.")
        return jsonify({'message': f'Error creating user: {str(e)}'}), 500

# Route untuk mengupdate saldo user
@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user_balance(user_id):
    try:
        data = request.get_json()
        if not data or 'balance' not in data:
            print(f"USER_SERVICE: Error - Missing balance data for user ID: {user_id}. Data: {data}")
            return jsonify({'message': 'Missing balance data'}), 400

        user = db.session.get(User, user_id) # Menggunakan db.session.get untuk primary key
        if not user:
            print(f"USER_SERVICE: Error - User ID: {user_id} not found for update.")
            return jsonify({'message': 'User not found'}), 404
            
        old_balance = user.balance
        user.balance = data['balance']
        db.session.commit()
        print(f"USER_SERVICE: Success - User ID: {user_id} balance updated from {old_balance} to {user.balance}.")
        
        return jsonify({'message': 'Balance updated successfully', 'balance': user.balance})
    except Exception as e:
        db.session.rollback()
        print(f"USER_SERVICE: Exception - Error updating balance for user ID: {user_id}: {str(e)}.")
        return jsonify({'message': f'Error updating balance: {str(e)}'}), 500


# Route untuk mendapatkan data user berdasarkan ID
@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            print(f"USER_SERVICE: Error - User ID: {user_id} not found.")
            return jsonify({'message': 'User not found'}), 404
        print(f"USER_SERVICE: Success - Fetched user '{user.username}' with ID: {user.id}.")
        return jsonify({
            'id': user.id,
            'username': user.username,
            'balance': user.balance
        })
    except Exception as e:
        print(f"USER_SERVICE: Exception - Error getting user ID: {user_id}: {str(e)}.")
        return jsonify({'message': f'Error getting user: {str(e)}'}), 500

# Route untuk mendapatkan data user berdasarkan username (digunakan oleh Auth Service)
@app.route('/users/by-username/<username>', methods=['GET'])
def get_user_by_username(username):
    try:
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"USER_SERVICE: Error - User with username '{username}' not found.")
            return jsonify({'message': 'User not found'}), 404
        print(f"USER_SERVICE: Success - Fetched user by username '{username}' (ID: {user.id}).")
        return jsonify({
            'id': user.id,
            'username': user.username,
            'password': user.password, # PERINGATAN: Dalam produksi, jangan kirim password!
            'balance': user.balance
        })
    except Exception as e:
        print(f"USER_SERVICE: Exception - Error getting user by username '{username}': {str(e)}.")
        return jsonify({'message': f'Error getting user by username: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        # WARNING: db.drop_all() akan MENGHAPUS SEMUA DATA!
        # Gunakan hanya dalam pengembangan atau jika Anda yakin ingin menghapus data.
        # db.drop_all() 
        db.create_all() # Membuat tabel jika belum ada
    print("USER_SERVICE: Starting on port 5001...")
    app.run(port=5001, debug=True)