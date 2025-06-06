from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import requests
import jwt
import datetime
import pymysql

pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app)

# Konfigurasi database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/iae_payment_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'

db = SQLAlchemy(app)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    transaction_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@app.route('/')
def index():
    return render_template('payment_service.html')

def verify_token(token):
    try:
        response = requests.post(
            'http://localhost:5002/auth/verify',
            headers={'Authorization': token}
        )
        return response.status_code == 200
    except:
        return False

@app.route('/payments', methods=['POST'])
def create_payment():
    token = request.headers.get('Authorization')
    if not token or not verify_token(token):
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    required_fields = ['booking_id', 'user_id', 'amount']
    
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing required fields'}), 400

    try:
        # Buat payment record
        payment = Payment(
            booking_id=data['booking_id'],
            user_id=data['user_id'],
            amount=data['amount'],
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        # Buat transaksi di transaction service
        transaction_data = {
            'user_id': data['user_id'],
            'amount': data['amount'],
            'type': 'withdrawal'
        }

        transaction_response = requests.post(
            'http://localhost:5003/transactions',
            headers={'Authorization': token},
            json=transaction_data
        )

        if transaction_response.status_code == 200:
            transaction_result = transaction_response.json()
            payment.transaction_id = transaction_result.get('transaction_id')
            payment.status = 'completed'
            db.session.commit()

            return jsonify({
                'message': 'Payment processed successfully',
                'payment_id': payment.id,
                'transaction_id': payment.transaction_id,
                'status': payment.status
            })
        else:
            payment.status = 'failed'
            db.session.commit()
            return jsonify({'message': 'Payment failed'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error processing payment: {str(e)}'}), 500

@app.route('/payments/booking/<int:booking_id>', methods=['GET'])
def get_payment_by_booking():
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
        'timestamp': payment.timestamp.isoformat()
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
        'amount': p.amount,
        'status': p.status,
        'transaction_id': p.transaction_id,
        'timestamp': p.timestamp.isoformat()
    } for p in payments])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5004, debug=True)