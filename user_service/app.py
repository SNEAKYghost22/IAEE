from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import requests
import pymysql
pymysql.install_as_MySQLdb()

app = Flask(__name__)

# Simplified CORS configuration
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Accept"], "expose_headers": ["Authorization"]}})

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/iae_user_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

@app.route('/')
def index():
    return render_template('user_service.html')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=0.0)

@app.route('/users', methods=['POST', 'OPTIONS'])
def create_user():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
        
        if 'username' not in data or 'password' not in data:
            return jsonify({'message': 'Missing required fields'}), 400

        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'message': 'Username already exists'}), 409

        new_user = User(
            username=data['username'],
            password=data['password'],
            balance=data.get('balance', 0.0)
        )
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user_id': new_user.id,
            'username': new_user.username
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating user: {str(e)}'}), 500

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user_balance(user_id):
    data = request.get_json()
    user = User.query.get_or_404(user_id)
    
    # Update balance with the new value
    user.balance = data['balance']
    db.session.commit()
    
    return jsonify({'message': 'Balance updated successfully', 'balance': user.balance})

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'balance': user.balance
    })

@app.route('/users/by-username/<username>', methods=['GET'])
def get_user_by_username(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'password': user.password,
        'balance': user.balance
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5001, debug=True)  # Enabling debug mode
