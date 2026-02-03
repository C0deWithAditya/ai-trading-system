"""
Authentication Routes for Trading AI Platform.
Handles login, signup, admin panel, and subscription pages.
"""

from flask import Blueprint, request, jsonify, redirect, make_response, Response
from functools import wraps
from user_auth import (
    get_user_manager, get_wallet_manager, get_payment_manager,
    SUBSCRIPTION_PLANS, init_admin
)

auth_bp = Blueprint('auth', __name__)

# Initialize admin on import
init_admin()


def get_current_user():
    """Get current user from cookie."""
    token = request.cookies.get('session_token')
    if not token:
        return None
    return get_user_manager().get_user_from_token(token)


def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({"error": "Login required"}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or not user.get('is_admin'):
            if request.headers.get('Accept', '').startswith('application/json'):
                return jsonify({"error": "Admin access required"}), 403
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def subscription_required(min_plan='free'):
    """Decorator to require minimum subscription level."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect('/login')
            
            plan_levels = {'free': 0, 'premium': 1, 'pro': 2}
            user_level = plan_levels.get(user.get('subscription', 'free'), 0)
            required_level = plan_levels.get(min_plan, 0)
            
            if user_level < required_level:
                return redirect('/subscribe')
            return f(*args, **kwargs)
        return decorated
    return decorator


# ============== AUTH PAGES ==============

@auth_bp.route('/login')
def login_page():
    """Login page."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - AI Trading System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }
        .login-card {
            background: rgba(30, 30, 50, 0.9);
            padding: 40px;
            border-radius: 20px;
            width: 100%;
            max-width: 400px;
            border: 1px solid rgba(139, 92, 246, 0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #a855f7, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .logo p { color: rgba(255,255,255,0.6); margin-top: 8px; }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: rgba(255,255,255,0.8);
            font-size: 14px;
        }
        .form-group input {
            width: 100%;
            padding: 14px 16px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            font-size: 16px;
            outline: none;
            transition: all 0.3s;
        }
        .form-group input:focus {
            border-color: #a855f7;
            box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.2);
        }
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #a855f7, #6366f1);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(168, 85, 247, 0.4);
        }
        .error {
            background: rgba(255, 71, 87, 0.1);
            border: 1px solid #ff4757;
            color: #ff4757;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: none;
        }
        .links {
            text-align: center;
            margin-top: 20px;
            color: rgba(255,255,255,0.6);
        }
        .links a {
            color: #a855f7;
            text-decoration: none;
        }
        .links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">
            <h1>🤖 AI Trading System</h1>
            <p>Login to access your dashboard</p>
        </div>
        
        <div id="error" class="error"></div>
        
        <form id="loginForm">
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="email" placeholder="Enter your email" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" placeholder="Enter your password" required>
            </div>
            <button type="submit" class="btn">Login</button>
        </form>
        
        <div class="links">
            Don't have an account? <a href="/signup">Sign up</a>
        </div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorDiv = document.getElementById('error');
            errorDiv.style.display = 'none';
            
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: document.getElementById('email').value,
                    password: document.getElementById('password').value,
                })
            });
            
            const data = await res.json();
            if (data.success) {
                window.location.href = '/';
            } else {
                errorDiv.textContent = data.error;
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''


@auth_bp.route('/signup')
def signup_page():
    """Signup page."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - AI Trading System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }
        .signup-card {
            background: rgba(30, 30, 50, 0.9);
            padding: 40px;
            border-radius: 20px;
            width: 100%;
            max-width: 420px;
            border: 1px solid rgba(139, 92, 246, 0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #a855f7, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .form-group { margin-bottom: 16px; }
        .form-group label {
            display: block; margin-bottom: 8px;
            color: rgba(255,255,255,0.8); font-size: 14px;
        }
        .form-group input {
            width: 100%; padding: 14px 16px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px; color: #fff; font-size: 16px;
            outline: none; transition: all 0.3s;
        }
        .form-group input:focus {
            border-color: #a855f7;
            box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.2);
        }
        .btn {
            width: 100%; padding: 14px;
            background: linear-gradient(135deg, #a855f7, #6366f1);
            border: none; border-radius: 10px; color: #fff;
            font-size: 16px; font-weight: 600; cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(168, 85, 247, 0.4);
        }
        .error, .success {
            padding: 12px; border-radius: 8px;
            margin-bottom: 20px; font-size: 14px; display: none;
        }
        .error { background: rgba(255, 71, 87, 0.1); border: 1px solid #ff4757; color: #ff4757; }
        .success { background: rgba(0, 210, 106, 0.1); border: 1px solid #00d26a; color: #00d26a; }
        .links { text-align: center; margin-top: 20px; color: rgba(255,255,255,0.6); }
        .links a { color: #a855f7; text-decoration: none; }
    </style>
</head>
<body>
    <div class="signup-card">
        <div class="logo">
            <h1>🤖 AI Trading System</h1>
            <p>Create your account</p>
        </div>
        
        <div id="error" class="error"></div>
        <div id="success" class="success"></div>
        
        <form id="signupForm">
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" id="name" placeholder="Enter your full name" required>
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="email" placeholder="Enter your email" required>
            </div>
            <div class="form-group">
                <label>Phone Number</label>
                <input type="tel" id="phone" placeholder="Enter phone number" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" placeholder="Create a password" required minlength="6">
            </div>
            <button type="submit" class="btn">Create Account</button>
        </form>
        
        <div class="links">
            Already have an account? <a href="/login">Login</a>
        </div>
    </div>
    
    <script>
        document.getElementById('signupForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorDiv = document.getElementById('error');
            const successDiv = document.getElementById('success');
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';
            
            const res = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: document.getElementById('name').value,
                    email: document.getElementById('email').value,
                    phone: document.getElementById('phone').value,
                    password: document.getElementById('password').value,
                })
            });
            
            const data = await res.json();
            if (data.success) {
                successDiv.textContent = 'Account created! Please wait for admin approval.';
                successDiv.style.display = 'block';
                document.getElementById('signupForm').reset();
            } else {
                errorDiv.textContent = data.error;
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''


# ============== AUTH API ==============

@auth_bp.route('/api/auth/signup', methods=['POST'])
def api_signup():
    """API: Create new user account."""
    data = request.json
    user_mgr = get_user_manager()
    
    result = user_mgr.create_user(
        email=data.get('email', ''),
        password=data.get('password', ''),
        name=data.get('name', ''),
        phone=data.get('phone', ''),
    )
    
    return jsonify(result)


@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    """API: Login user."""
    data = request.json
    user_mgr = get_user_manager()
    
    result = user_mgr.login(
        email=data.get('email', ''),
        password=data.get('password', ''),
    )
    
    if result['success']:
        resp = make_response(jsonify(result))
        resp.set_cookie('session_token', result['token'], httponly=True, samesite='Lax', max_age=7*24*60*60)
        return resp
    
    return jsonify(result)


@auth_bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API: Logout user."""
    token = request.cookies.get('session_token')
    if token:
        get_user_manager().logout(token)
    
    resp = make_response(jsonify({"success": True}))
    resp.delete_cookie('session_token')
    return resp


@auth_bp.route('/api/auth/me')
def api_me():
    """API: Get current user."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    
    # Add wallet balance
    wallet = get_wallet_manager()
    user_data = {k: v for k, v in user.items() if k != 'password'}
    user_data['wallet_balance'] = wallet.get_balance(user['email'])
    
    return jsonify(user_data)


# ============== SUBSCRIPTION API ==============

@auth_bp.route('/api/subscription/plans')
def api_plans():
    """Get available subscription plans."""
    return jsonify(SUBSCRIPTION_PLANS)


@auth_bp.route('/api/wallet/balance')
@login_required
def api_wallet_balance():
    """Get user wallet balance."""
    user = get_current_user()
    wallet = get_wallet_manager()
    
    return jsonify({
        "balance": wallet.get_balance(user['email']),
        "transactions": wallet.get_transactions(user['email']),
    })


@auth_bp.route('/api/payment/create', methods=['POST'])
@login_required
def api_create_payment():
    """Create a payment request."""
    user = get_current_user()
    data = request.json
    
    payment_mgr = get_payment_manager()
    payment = payment_mgr.create_payment_request(
        email=user['email'],
        amount=float(data.get('amount', 0)),
        name=data.get('name', user['name']),
        phone=data.get('phone', user.get('phone', '')),
    )
    
    upi_link = payment_mgr.get_upi_link(payment['amount'], payment['id'])
    
    return jsonify({
        "payment": payment,
        "upi_link": upi_link,
        "upi_id": payment_mgr.upi_id,
        "upi_name": payment_mgr.upi_name,
    })


@auth_bp.route('/api/subscription/purchase', methods=['POST'])
@login_required
def api_purchase_subscription():
    """Purchase subscription using wallet balance."""
    user = get_current_user()
    data = request.json
    plan = data.get('plan', 'premium')
    
    if plan not in SUBSCRIPTION_PLANS:
        return jsonify({"error": "Invalid plan"}), 400
    
    price = SUBSCRIPTION_PLANS[plan]['price']
    wallet = get_wallet_manager()
    
    if wallet.get_balance(user['email']) < price:
        return jsonify({"error": "Insufficient wallet balance"}), 400
    
    # Deduct from wallet
    wallet.deduct_balance(user['email'], price, f"Subscription: {plan}")
    
    # Activate subscription
    user_mgr = get_user_manager()
    user_mgr.update_subscription(user['email'], plan)
    
    return jsonify({"success": True, "plan": plan})


# ============== ADMIN API ==============

@auth_bp.route('/api/admin/users')
@admin_required
def api_admin_users():
    """Get all users (admin only)."""
    user_mgr = get_user_manager()
    wallet_mgr = get_wallet_manager()
    
    users = user_mgr.get_all_users()
    for user in users:
        user['wallet_balance'] = wallet_mgr.get_balance(user['email'])
    
    return jsonify(users)


@auth_bp.route('/api/admin/approve/<email>', methods=['POST'])
@admin_required
def api_admin_approve(email):
    """Approve a user (admin only)."""
    user_mgr = get_user_manager()
    if user_mgr.approve_user(email):
        return jsonify({"success": True})
    return jsonify({"error": "User not found"}), 404


@auth_bp.route('/api/admin/pending_payments')
@admin_required
def api_admin_pending_payments():
    """Get pending payments (admin only)."""
    payment_mgr = get_payment_manager()
    return jsonify(payment_mgr.get_pending_payments())


@auth_bp.route('/api/admin/approve_payment/<payment_id>', methods=['POST'])
@admin_required
def api_admin_approve_payment(payment_id):
    """Approve a payment (admin only)."""
    user = get_current_user()
    payment_mgr = get_payment_manager()
    
    if payment_mgr.approve_payment(payment_id, user['email']):
        return jsonify({"success": True})
    return jsonify({"error": "Payment not found or already processed"}), 404


@auth_bp.route('/api/admin/assign_subscription', methods=['POST'])
@admin_required
def api_admin_assign_subscription():
    """Manually assign subscription to user (admin only)."""
    data = request.json
    email = data.get('email')
    plan = data.get('plan', 'premium')
    days = data.get('days', 30)
    
    user_mgr = get_user_manager()
    if user_mgr.update_subscription(email, plan, days):
        return jsonify({"success": True})
    return jsonify({"error": "User not found"}), 404


@auth_bp.route('/api/admin/add_wallet_balance', methods=['POST'])
@admin_required
def api_admin_add_balance():
    """Manually add wallet balance (admin only)."""
    data = request.json
    email = data.get('email')
    amount = float(data.get('amount', 0))
    
    wallet_mgr = get_wallet_manager()
    wallet_mgr.add_balance(email, amount, "Admin manual credit")
    
    return jsonify({"success": True, "new_balance": wallet_mgr.get_balance(email)})


@auth_bp.route('/api/admin/settings')
@admin_required
def api_admin_get_settings():
    """Get admin settings (admin only)."""
    payment_mgr = get_payment_manager()
    return jsonify(payment_mgr.get_settings())


@auth_bp.route('/api/admin/settings', methods=['POST'])
@admin_required
def api_admin_update_settings():
    """Update admin settings (admin only)."""
    data = request.json
    payment_mgr = get_payment_manager()
    
    upi_id = data.get('upi_id', payment_mgr.upi_id)
    upi_name = data.get('upi_name', payment_mgr.upi_name)
    
    payment_mgr.update_upi_settings(upi_id, upi_name)
    
    return jsonify({"success": True, "settings": payment_mgr.get_settings()})
