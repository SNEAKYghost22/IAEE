from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import requests
import datetime
import pymysql
import random 
import string 

pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app)

# Konfigurasi Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/iae_reward_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'super-secret-key-bankin-app' 

db = SQLAlchemy(app)

# --- Model Database ---

class UserReward(db.Model):
    """Menyimpan total poin untuk setiap pengguna."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, unique=True)
    points = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class PointTransaction(db.Model):
    """Mencatat setiap transaksi perolehan atau penukaran poin."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    payment_id = db.Column(db.Integer, nullable=True)
    points = db.Column(db.Integer, nullable=False)  # Positif (earn) atau negatif (redeem)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'earn', 'redeem', 'redeem_item'
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class RewardItem(db.Model):
    """Menyimpan daftar item yang bisa ditukar dengan poin."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    points_cost = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class RedemptionCode(db.Model):
    """Menyimpan kode unik yang dihasilkan dari penukaran poin."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    point_transaction_id = db.Column(db.Integer, db.ForeignKey('point_transaction.id'))
    reward_item_id = db.Column(db.Integer, db.ForeignKey('reward_item.id'), nullable=True)
    code = db.Column(db.String(12), unique=True, nullable=False)
    discount_amount = db.Column(db.Float, nullable=True) # Untuk redeem biasa
    is_used = db.Column(db.Boolean, default=False)
    generated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)


# --- Fungsi Helper ---

def verify_token(token):
    """Fungsi untuk memverifikasi token dengan Auth Service."""
    try:
        if not token or not token.startswith('Bearer '):
            return False
        
        auth_response = requests.post(
            'http://localhost:5002/auth/verify',
            headers={'Authorization': token},
            json={},
            timeout=5
        )
        if auth_response.ok:
            auth_data = auth_response.json()
            return auth_data.get('status') == 'success' and auth_data.get('data', {}).get('valid')
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"REWARD_SERVICE: Connection/Request error to Auth Service: {e}")
        return False

def generate_unique_code(length=8):
    """Menghasilkan kode unik untuk penukaran."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if not RedemptionCode.query.filter_by(code=code).first():
            return code

def calculate_points(amount):
    """Menghitung poin dari jumlah pembayaran (1 poin per 10.000)."""
    return int(amount // 10000)

def calculate_discount_amount(points_redeemed):
    """Menghitung nilai diskon dari poin (10 poin = Rp 5.000)."""
    if points_redeemed > 0 and points_redeemed % 10 == 0:
        return (points_redeemed // 10) * 5000
    return 0

# --- Routes / Endpoints ---

@app.route('/')
def index_reward():
    return render_template('reward_service.html')

@app.route('/rewards/earn', methods=['POST'])
def earn_points():
    token = request.headers.get('Authorization')
    if not verify_token(token):
        return jsonify({'message': 'Invalid or missing token'}), 401

    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    payment_id = data.get('payment_id')

    if not all([user_id, amount is not None, payment_id]):
        return jsonify({'message': 'Missing required fields (user_id, amount, payment_id)'}), 400

    earned_points = calculate_points(float(amount))
    if earned_points <= 0:
        return jsonify({'message': 'No points earned for this amount', 'earned_points': 0}), 200

    try:
        user_reward = UserReward.query.filter_by(user_id=user_id).first()
        if not user_reward:
            user_reward = UserReward(user_id=user_id, points=0)
            db.session.add(user_reward)
        
        user_reward.points += earned_points
        
        point_tx = PointTransaction(
            user_id=user_id, payment_id=payment_id,
            points=earned_points, transaction_type='earn'
        )
        db.session.add(point_tx)
        db.session.commit()

        return jsonify({
            'message': 'Points earned successfully',
            'earned_points': earned_points,
            'current_points': user_reward.points
        }), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in earn_points: {e}")
        return jsonify({'message': 'An internal error occurred'}), 500

@app.route('/rewards/redeem', methods=['POST'])
def redeem_points():
    token = request.headers.get('Authorization')
    if not verify_token(token):
        return jsonify({'message': 'Invalid or missing token'}), 401
    
    data = request.get_json()
    user_id = data.get('user_id')
    points_to_redeem = data.get('points')

    if not all([user_id, points_to_redeem]):
        return jsonify({'message': 'Missing fields (user_id, points)'}), 400

    if not isinstance(points_to_redeem, int) or points_to_redeem <= 0 or points_to_redeem % 10 != 0:
        return jsonify({'message': 'Points must be a positive integer and a multiple of 10'}), 400

    try:
        user_reward = UserReward.query.filter_by(user_id=user_id).first()
        if not user_reward or user_reward.points < points_to_redeem:
            return jsonify({'message': 'Insufficient points'}), 400

        discount_amount = calculate_discount_amount(points_to_redeem)
        if discount_amount == 0:
            return jsonify({'message': 'Points do not qualify for a discount'}), 400

        user_reward.points -= points_to_redeem
        
        point_tx = PointTransaction(user_id=user_id, points=-points_to_redeem, transaction_type='redeem')
        db.session.add(point_tx)
        db.session.flush() # To get point_tx.id for the foreign key

        redemption_code = RedemptionCode(
            user_id=user_id,
            point_transaction_id=point_tx.id,
            code=generate_unique_code(10),
            discount_amount=discount_amount,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=30)
        )
        db.session.add(redemption_code)
        db.session.commit()

        return jsonify({
            'message': 'Points redeemed successfully',
            'points_redeemed': points_to_redeem,
            'discount_amount': discount_amount,
            'discount_code': redemption_code.code,
            'remaining_points': user_reward.points
        }), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in redeem_points: {e}")
        return jsonify({'message': 'An internal error occurred'}), 500

@app.route('/rewards/points/<int:user_id>', methods=['GET'])
def get_user_points(user_id):
    token = request.headers.get('Authorization')
    if not verify_token(token):
        return jsonify({'message': 'Invalid or missing token'}), 401
    
    user_reward = UserReward.query.filter_by(user_id=user_id).first()
    points = user_reward.points if user_reward else 0
    
    transactions = PointTransaction.query.filter_by(user_id=user_id).order_by(PointTransaction.created_at.desc()).all()
    
    return jsonify({
        'user_id': user_id,
        'points': points,
        'point_transactions': [{
            'id': t.id, 'points': t.points, 'transaction_type': t.transaction_type,
            'created_at': t.created_at.isoformat()
        } for t in transactions]
    })

@app.route('/rewards/items', methods=['GET'])
def get_reward_items():
    items = RewardItem.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': item.id, 'name': item.name, 'description': item.description, 'points_cost': item.points_cost
    } for item in items])

@app.route('/rewards/redeem_item', methods=['POST'])
def redeem_reward_item():
    token = request.headers.get('Authorization')
    if not verify_token(token):
        return jsonify({'message': 'Invalid or missing token'}), 401

    data = request.get_json()
    user_id = data.get('user_id')
    item_id = data.get('reward_item_id')

    if not all([user_id, item_id]):
        return jsonify({'message': 'Missing fields (user_id, reward_item_id)'}), 400

    try:
        item = RewardItem.query.get(item_id)
        if not item or not item.is_active:
            return jsonify({'message': 'Reward item not found or is inactive'}), 404

        user_reward = UserReward.query.filter_by(user_id=user_id).first()
        if not user_reward or user_reward.points < item.points_cost:
            return jsonify({'message': 'Insufficient points for this item'}), 400
            
        user_reward.points -= item.points_cost

        point_tx = PointTransaction(user_id=user_id, points=-item.points_cost, transaction_type='redeem_item')
        db.session.add(point_tx)
        db.session.flush()

        redemption = RedemptionCode(
            user_id=user_id,
            point_transaction_id=point_tx.id,
            reward_item_id=item.id,
            code=generate_unique_code(12),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=90)
        )
        db.session.add(redemption)
        db.session.commit()

        return jsonify({
            'message': 'Reward item redeemed successfully',
            'reward_name': item.name,
            'redemption_code': redemption.code,
            'remaining_points': user_reward.points
        }), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in redeem_reward_item: {e}")
        return jsonify({'message': 'An internal error occurred'}), 500

@app.route('/rewards/redeemed_codes/<int:user_id>', methods=['GET'])
def get_redeemed_codes(user_id):
    token = request.headers.get('Authorization')
    if not verify_token(token):
        return jsonify({'message': 'Invalid or missing token'}), 401
    
    codes = db.session.query(
        RedemptionCode, RewardItem.name
    ).outerjoin(RewardItem, RedemptionCode.reward_item_id == RewardItem.id)\
     .filter(RedemptionCode.user_id == user_id)\
     .order_by(RedemptionCode.generated_at.desc())\
     .all()

    result = []
    for redemption, reward_name in codes:
        result.append({
            'code': redemption.code,
            'reward_name': reward_name or f"Voucher Diskon Rp {int(redemption.discount_amount):,}",
            'generated_at': redemption.generated_at.isoformat(),
            'expires_at': redemption.expires_at.isoformat() if redemption.expires_at else None,
            'is_used': redemption.is_used
        })
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seeding data dummy jika tabel RewardItem kosong
        if not RewardItem.query.first():
            items = [
                RewardItem(name="Voucher Kopi Gratis", description="Tukar dengan satu gelas Americano di kafe rekanan.", points_cost=50),
                RewardItem(name="Potongan Ongkir", description="Dapatkan potongan ongkos kirim hingga Rp 20.000.", points_cost=100),
                RewardItem(name="T-Shirt Eksklusif BankIn", description="Kaos edisi terbatas dengan logo BankIn.", points_cost=250)
            ]
            db.session.bulk_save_objects(items)
            db.session.commit()
            print("REWARD_SERVICE: Dummy reward items have been seeded.")
            
    print("REWARD_SERVICE: Starting on port 5005...")
    app.run(port=5005, debug=True)