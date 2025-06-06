from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify, request, render_template

from flask_cors import CORS
import requests

import pymysql
pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Accept"], "expose_headers": ["Authorization"]}})
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/transaction_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'withdrawal' or 'deposit'
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

@app.route('/')
def index():
    return render_template('transaction_service.html')

@app.route('/transactions', methods=['POST'])
def create_transaction():
    data = request.get_json()
    token = request.headers.get('Authorization')
    
    # Verifying token
    auth_response = requests.post('http://localhost:5002/auth/verify', headers={'Authorization': token})
    print(f"Auth Response: {auth_response.text}")  # Debugging: Log response
    if not auth_response.json().get('valid'):
        return jsonify({'message': 'Unauthorized'}), 401
    
    # Check user balance from User Service
    user_response = requests.get(f'http://localhost:5001/users/{data["user_id"]}')
    print(f"User Response: {user_response.text}")  # Debugging: Log response
    user = user_response.json()
    
    # If withdrawal, ensure sufficient balance
    if data['type'] == 'withdrawal' and user['balance'] < data['amount']:
        return jsonify({'message': 'Insufficient balance'}), 400
    
    # Update balance based on transaction type
    if data['type'] == 'withdrawal':
        new_balance = user['balance'] - data['amount']  # Balance decreases
    elif data['type'] == 'deposit':
        new_balance = user['balance'] + data['amount']  # Balance increases
    
    # Update balance in User Service
    update_response = requests.put(f'http://localhost:5001/users/{data["user_id"]}', json={'balance': new_balance})
    print(f"Update Response: {update_response.text}")  # Debugging: Log response
    
    if update_response.status_code != 200:
        return jsonify({'message': 'Failed to update user balance'}), 500
    
    # Add transaction to the database
    new_transaction = Transaction(user_id=data['user_id'], amount=data['amount'], type=data['type'])
    db.session.add(new_transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Transaction created successfully',
        'transaction_id': new_transaction.id
    }), 201

    
    # Add transaction to the database
    new_transaction = Transaction(user_id=data['user_id'], amount=data['amount'], type=data['type'])
    db.session.add(new_transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Transaction created successfully',
        'transaction_id': new_transaction.id
    }), 201

@app.route('/transactions/user/<int:user_id>', methods=['GET'])
def get_user_transactions(user_id):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing'}), 401
        
    # Verifying token
    auth_response = requests.post('http://localhost:5002/auth/verify', headers={'Authorization': token})
    if not auth_response.ok:
        return jsonify({'message': 'Failed to verify token'}), 401

    auth_data = auth_response.json()
    if not auth_data.get('valid'):
        return jsonify({'message': 'Invalid token'}), 401

    transactions = Transaction.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'id': t.id,
        'amount': t.amount,
        'type': t.type,
        'timestamp': t.timestamp.isoformat()
    } for t in transactions])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5003)
