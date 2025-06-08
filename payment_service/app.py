from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import requests
import jwt
import datetime
import pymysql
import random 
import string 

pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app) # CORS(app) cukup, karena Anda sudah mengatur CORS di setiap file HTML

# Konfigurasi database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/iae_payment_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# PENTING: PASTIKAN SECRET_KEY INI SAMA DI SEMUA SERVICE (auth, reward)
app.config['SECRET_KEY'] = 'super-secret-key-bankin-app' 

db = SQLAlchemy(app)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, failed
    transaction_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Tambahan field dari booking service
    customer_name = db.Column(db.String(100), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=False)
    booked_seat_ids = db.Column(db.JSON, nullable=False)
    payment_code = db.Column(db.String(10), unique=True, nullable=False)

def verify_token(token):
    """Fungsi untuk memverifikasi token dengan Auth Service."""
    try:
        if token.startswith('Bearer '):
            token = token.split(' ')[1]
        
        auth_response = requests.post(
            'http://localhost:5002/auth/verify',
            headers={'Authorization': f'Bearer {token}'},
            json={},
            timeout=5 # Tambahkan timeout
        )
        if auth_response.ok:
            auth_data = auth_response.json()
            return auth_data.get('status') == 'success' and auth_data.get('data', {}).get('valid')
        print(f"PAYMENT_SERVICE: Error - Token verification failed via Auth Service. Status: {auth_response.status_code}, Response: {auth_response.text}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"PAYMENT_SERVICE: Error - Connection to Auth Service failed: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"PAYMENT_SERVICE: Error - Request to Auth Service failed: {e}")
        return False
    except Exception as e:
        print(f"PAYMENT_SERVICE: Exception - Unexpected error during token verification: {str(e)}")
        return False

@app.route('/')
def index_payment():
    return render_template('payment_service.html')

@app.route('/payments', methods=['POST'])
def create_payment():
    token = request.headers.get('Authorization')
    if not token:
        print("PAYMENT_SERVICE: Error - Token is missing for create_payment.")
        return jsonify({'message': 'Token is missing'}), 401

    # Verifikasi token
    if not verify_token(token): 
        print("PAYMENT_SERVICE: Error - Token verification failed for create_payment.")
        return jsonify({'message': 'Failed to verify token'}), 401

    data = request.get_json()
    required_fields = ['booking_id', 'user_id', 'amount', 'customer_name', 'ticket_id', 'booked_seat_ids']
    
    if not all(field in data for field in required_fields):
        print(f"PAYMENT_SERVICE: Error - Missing required fields: {data}")
        return jsonify({'message': f'Missing required fields: {", ".join(required_fields)}'}), 400

    amount = data.get('amount')
    MAX_PAYMENT_AMOUNT = 10000000 # Rp 10.000.000
    
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        print(f"PAYMENT_SERVICE: Error - Invalid amount provided: {amount}. Must be a positive number.")
        return jsonify({'message': 'Invalid amount provided. Must be a positive number.'}), 400
    
    if amount > MAX_PAYMENT_AMOUNT:
        print(f"PAYMENT_SERVICE: Error - Payment amount {amount} exceeds max limit {MAX_PAYMENT_AMOUNT}.")
        return jsonify({'message': f'Payment amount exceeds the maximum limit of Rp {MAX_PAYMENT_AMOUNT:,}.'}), 400

    try:
        payment_code = generate_payment_code()
        print(f"PAYMENT_SERVICE: Generated payment code: {payment_code}")

        payment = Payment(
            booking_id=data['booking_id'],
            user_id=data['user_id'],
            amount=amount,
            status='pending',
            customer_name=data['customer_name'],
            ticket_id=data['ticket_id'],
            booked_seat_ids=data['booked_seat_ids'],
            payment_code=payment_code
        )
        db.session.add(payment)
        db.session.commit()
        print(f"PAYMENT_SERVICE: Success - Payment record created (ID: {payment.id}, Status: pending).")

        transaction_data = {
            'user_id': data['user_id'],
            'amount': amount, 
            'type': 'withdrawal',
            'description': f'Payment for booking {data["booking_id"]} with code {payment_code}'
        }

        print(f"PAYMENT_SERVICE: Calling Transaction Service for user {data['user_id']} with amount {amount}...")
        transaction_response = requests.post(
            'http://localhost:5003/transactions',
            headers={'Authorization': token, 'Content-Type': 'application/json'},
            json=transaction_data,
            timeout=10 
        )

        if transaction_response.status_code == 201:
            transaction_result = transaction_response.json()
            payment.transaction_id = transaction_result.get('transaction_id')
            payment.status = 'completed'
            db.session.commit() 
            print(f"PAYMENT_SERVICE: Success - Transaction Service successful. Payment ID {payment.id} set to completed. Transaction ID: {payment.transaction_id}")

            # PANGGIL REWARD SERVICE UNTUK MENAMBAH POIN
            try:
                print(f"PAYMENT_SERVICE: Calling Reward Service to earn points for user {data['user_id']}...")
                reward_response = requests.post(
                    'http://localhost:5005/rewards/earn',
                    headers={'Authorization': token, 'Content-Type': 'application/json'},
                    json={
                        'user_id': data['user_id'],
                        'payment_id': payment.id, 
                        'amount': amount
                    },
                    timeout=10 
                )
                if not reward_response.ok:
                    print(f"PAYMENT_SERVICE: Warning - Failed to earn points for user {data['user_id']}. Status: {reward_response.status_code}, Response: {reward_response.text}")
                else:
                    print(f"PAYMENT_SERVICE: Success - Points earned successfully for user {data['user_id']}.")
            except requests.exceptions.ConnectionError as e:
                print(f"PAYMENT_SERVICE: Error - Connection to Reward Service failed: {e}")
            except requests.exceptions.RequestException as e:
                print(f"PAYMENT_SERVICE: Error - Request to Reward Service failed: {e}")
            except Exception as e:
                print(f"PAYMENT_SERVICE: Exception - Unexpected error calling Reward Service: {str(e)}")

            return jsonify({
                'message': 'Payment processed successfully and points earned (if applicable)',
                'payment_id': payment.id,
                'transaction_id': payment.transaction_id,
                'status': payment.status,
                'payment_code': payment.payment_code
            })
        else:
            # Jika transaksi di Transaction Service gagal, batalkan pembayaran ini juga
            payment.status = 'failed'
            db.session.commit()
            print(f"PAYMENT_SERVICE: Error - Transaction Service failed. Payment ID {payment.id} set to failed. Status: {transaction_response.status_code}, Details: {transaction_response.text}")
            return jsonify({
                'message': 'Payment failed due to an issue with transaction processing',
                'details': transaction_response.json() # Pass actual error details from transaction service
            }), 400

    except Exception as e:
        db.session.rollback() 
        print(f"PAYMENT_SERVICE: Exception - Unexpected error processing payment: {str(e)}")
        return jsonify({'message': f'Error processing payment: {str(e)}'}), 500

@app.route('/payments/booking/<int:booking_id>', methods=['GET'])
def get_payment_by_booking(booking_id):
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({'message': 'Unauthorized'}), 401

    payment = Payment.query.filter_by(booking_id=booking_id).first()
    if not payment:
        return jsonify({'message': 'Payment not found'}), 404

    return jsonify({
        'id': payment.id,
        'booking_id': payment.booking_id,
        'user_id': payment.user_id,
        'amount': payment.amount,
        'status': payment.status,
        'transaction_id': payment.transaction_id,
        'timestamp': payment.timestamp.isoformat(),
        'customer_name': payment.customer_name,
        'ticket_id': payment.ticket_id,
        'booked_seat_ids': payment.booked_seat_ids, 
        'payment_code': payment.payment_code
    })

@app.route('/payments/user/<int:user_id>', methods=['GET'])
def get_user_payments(user_id):
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({'message': 'Unauthorized'}), 401

    payments = Payment.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'id': p.id,
        'booking_id': p.booking_id,
        'user_id': p.user_id,
        'amount': p.amount,
        'status': p.status,
        'transaction_id': p.transaction_id,
        'timestamp': p.timestamp.isoformat(),
        'customer_name': p.customer_name,
        'ticket_id': p.ticket_id,
        'booked_seat_ids': p.booked_seat_ids, 
        'payment_code': p.payment_code
    } for p in payments])

def generate_payment_code():
    """Menghasilkan kode pembayaran unik."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Payment.query.filter_by(payment_code=code).first():
            return code

if __name__ == '__main__':
    with app.app_context():
        # WARNING: db.drop_all() will delete all data! Use only for development.
        # db.drop_all() 
        db.create_all() 
    print("PAYMENT_SERVICE: Starting on port 5004...")
    app.run(port=5004, debug=True)