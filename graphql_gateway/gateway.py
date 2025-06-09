import httpx
from ariadne import QueryType, MutationType, ObjectType, make_executable_schema, load_schema_from_path
from ariadne.asgi import GraphQL

# --- Konfigurasi Alamat Layanan Mikro ---
USER_SERVICE_URL = "http://localhost:5001"
AUTH_SERVICE_URL = "http://localhost:5002"
TRANSACTION_SERVICE_URL = "http://localhost:5003"
PAYMENT_SERVICE_URL = "http://localhost:5004"
REWARD_SERVICE_URL = "http://localhost:5005"

# --- Muat Skema dari File ---
type_defs = load_schema_from_path("schema.graphql")

# --- Inisialisasi Tipe Query dan Mutation ---
query = QueryType()
mutation = MutationType()

# --- Inisialisasi Tipe Objek untuk Relasi ---
user = ObjectType("User")
payment = ObjectType("Payment")

# =================================================
# RESOLVERS UNTUK TIPE QUERY
# =================================================

@query.field("me")
def resolve_me(_, info):
    # Dapatkan token dari header permintaan
    request = info.context["request"]
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None
    
    # Verifikasi token ke Auth Service
    with httpx.Client() as client:
        response = client.post(f"{AUTH_SERVICE_URL}/auth/verify", headers={"Authorization": auth_header})
        if response.status_code != 200:
            return None
        user_data = response.json().get("data")
        if not user_data or not user_data.get("valid"):
            return None
        
        # Ambil detail user dari User Service
        user_id = user_data["user_id"]
        user_response = client.get(f"{USER_SERVICE_URL}/users/{user_id}")
        return user_response.json() if user_response.status_code == 200 else None

@query.field("user")
def resolve_user(_, info, id):
    with httpx.Client() as client:
        response = client.get(f"{USER_SERVICE_URL}/users/{id}")
        return response.json() if response.status_code == 200 else None

@query.field("myPayments")
def resolve_my_payments(_, info):
    # Gunakan resolver 'me' untuk mendapatkan user_id dari token
    user = resolve_me(_, info)
    if not user:
        return []
    
    request = info.context["request"]
    auth_header = request.headers.get("authorization")
    
    with httpx.Client() as client:
        response = client.get(f"{PAYMENT_SERVICE_URL}/payments/user/{user['id']}", headers={"Authorization": auth_header})
        return response.json() if response.status_code == 200 else []

# Implementasi serupa untuk myTransactions, availableRewardItems, myRedeemedCodes...
@query.field("myTransactions")
def resolve_my_transactions(_, info):
    user = resolve_me(_, info)
    if not user: return []
    headers = {"Authorization": info.context["request"].headers.get("authorization")}
    with httpx.Client() as client:
        r = client.get(f"{TRANSACTION_SERVICE_URL}/transactions/user/{user['id']}", headers=headers)
        return r.json() if r.status_code == 200 else []

@query.field("availableRewardItems")
def resolve_available_reward_items(_, info):
    with httpx.Client() as client:
        r = client.get(f"{REWARD_SERVICE_URL}/rewards/items")
        return r.json() if r.status_code == 200 else []

@query.field("myRedeemedCodes")
def resolve_my_redeemed_codes(_, info):
    user = resolve_me(_, info)
    if not user: return []
    headers = {"Authorization": info.context["request"].headers.get("authorization")}
    with httpx.Client() as client:
        r = client.get(f"{REWARD_SERVICE_URL}/rewards/redeemed_codes/{user['id']}", headers=headers)
        return r.json() if r.status_code == 200 else []


# =================================================
# RESOLVERS UNTUK TIPE MUTATION
# =================================================

@mutation.field("login")
def resolve_login(_, info, username, password):
    with httpx.Client() as client:
        response = client.post(f"{AUTH_SERVICE_URL}/auth/login", json={"username": username, "password": password})
        return response.json()

@mutation.field("createUser")
def resolve_create_user(_, info, username, password, initialBalance):
    with httpx.Client() as client:
        response = client.post(f"{USER_SERVICE_URL}/users", json={"username": username, "password": password, "balance": initialBalance})
        return response.json()

@mutation.field("createPayment")
def resolve_create_payment(_, info, **data):
    # 'data' akan berisi semua argumen: bookingId, userId, dll.
    request = info.context["request"]
    auth_header = request.headers.get("authorization")
    with httpx.Client() as client:
        response = client.post(f"{PAYMENT_SERVICE_URL}/payments", json=data, headers={"Authorization": auth_header})
        return response.json()
        
# Implementasi serupa untuk createTransaction, redeemPointsForDiscount, dll.
@mutation.field("createTransaction")
def resolve_create_transaction(_, info, amount, type):
    user = resolve_me(_, info)
    if not user: raise Exception("Authentication required.")
    headers = {"Authorization": info.context["request"].headers.get("authorization")}
    payload = {"user_id": user['id'], "amount": amount, "type": type}
    with httpx.Client() as client:
        r = client.post(f"{TRANSACTION_SERVICE_URL}/transactions", json=payload, headers=headers)
        return r.json()

@mutation.field("redeemPointsForDiscount")
def resolve_redeem_points(_, info, points):
    user = resolve_me(_, info)
    if not user: raise Exception("Authentication required.")
    headers = {"Authorization": info.context["request"].headers.get("authorization")}
    payload = {"user_id": user['id'], "points": points}
    with httpx.Client() as client:
        r = client.post(f"{REWARD_SERVICE_URL}/rewards/redeem", json=payload, headers=headers)
        # Nama field di GQL adalah 'rewardName', di REST 'reward_name'. Perlu disamakan.
        data = r.json()
        data['rewardName'] = f"Voucher Diskon Rp {int(data.get('discount_amount', 0)):,}"
        return data
        
@mutation.field("redeemRewardItem")
def resolve_redeem_reward_item(_, info, itemId):
    user = resolve_me(_, info)
    if not user: raise Exception("Authentication required.")
    headers = {"Authorization": info.context["request"].headers.get("authorization")}
    payload = {"user_id": user['id'], "reward_item_id": int(itemId)}
    with httpx.Client() as client:
        r = client.post(f"{REWARD_SERVICE_URL}/rewards/redeem_item", json=payload, headers=headers)
        data = r.json()
        data['rewardName'] = data.get('reward_name')
        return data
# ... (setelah inisialisasi user dan payment)
reward_item = ObjectType("RewardItem")
@reward_item.field("pointsCost")
def resolve_points_cost(item_obj, _):
    # 'item_obj' adalah data JSON yang diterima, mis: {'id': 1, 'points_cost': 100}
    # Kita ambil nilainya dari kunci 'points_cost' (dengan underscore)
    return item_obj.get("points_cost")
# =================================================
# RESOLVERS UNTUK RELASI ANTAR TIPE
# =================================================

@user.field("payments")
def resolve_user_payments(user_obj, info):
    # user_obj berisi hasil dari resolver parent, yaitu data User
    user_id = user_obj['id']
    auth_header = info.context["request"].headers.get("authorization")
    with httpx.Client() as client:
        response = client.get(f"{PAYMENT_SERVICE_URL}/payments/user/{user_id}", headers={"Authorization": auth_header})
        return response.json() if response.status_code == 200 else []
        
# Implementasi serupa untuk relasi lainnya...
@user.field("transactions")
def resolve_user_transactions(user_obj, info):
    user_id = user_obj['id']
    auth_header = info.context["request"].headers.get("authorization")
    with httpx.Client() as client:
        r = client.get(f"{TRANSACTION_SERVICE_URL}/transactions/user/{user_id}", headers={"Authorization": auth_header})
        return r.json() if r.status_code == 200 else []

@user.field("rewards")
def resolve_user_rewards(user_obj, info):
    user_id = user_obj['id']
    auth_header = info.context["request"].headers.get("authorization")
    with httpx.Client() as client:
        r = client.get(f"{REWARD_SERVICE_URL}/rewards/points/{user_id}", headers={"Authorization": auth_header})
        data = r.json()
        # Sesuaikan nama field dari response REST ke skema GraphQL
        return {"userId": data["user_id"], "points": data["points"], "history": data["point_transactions"]}

# --- Buat Skema yang Bisa Dieksekusi ---
schema = make_executable_schema(type_defs, query, mutation, user, payment, reward_item)

# --- Buat Aplikasi ASGI ---
app = GraphQL(schema, debug=True)