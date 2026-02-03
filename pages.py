"""
Subscription, Payment, and Admin Pages for Trading AI Platform.
"""

from flask import Blueprint
from auth_routes import login_required, admin_required, get_current_user
from user_auth import SUBSCRIPTION_PLANS, get_payment_manager

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/subscribe')
@login_required
def subscribe_page():
    """Subscription plans page."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subscribe - AI Trading System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh; color: #fff; padding: 40px 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 50px; }
        .header h1 {
            font-size: 36px; margin-bottom: 10px;
            background: linear-gradient(135deg, #a855f7, #6366f1);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .header p { color: rgba(255,255,255,0.6); }
        .wallet-card {
            background: rgba(30, 30, 50, 0.9); padding: 20px 30px;
            border-radius: 16px; display: flex; justify-content: space-between;
            align-items: center; margin-bottom: 40px;
            border: 1px solid rgba(139, 92, 246, 0.3);
        }
        .wallet-balance { font-size: 32px; font-weight: 700; color: #00d26a; }
        .wallet-label { color: rgba(255,255,255,0.6); font-size: 14px; }
        .add-money-btn {
            padding: 12px 24px; background: linear-gradient(135deg, #00d26a, #00a854);
            border: none; border-radius: 10px; color: #fff; font-weight: 600;
            cursor: pointer; font-size: 14px;
        }
        .plans-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
        .plan-card {
            background: rgba(30, 30, 50, 0.9); border-radius: 20px; padding: 30px;
            border: 1px solid rgba(255,255,255,0.1); text-align: center;
            transition: transform 0.3s, border-color 0.3s;
        }
        .plan-card:hover { transform: translateY(-5px); border-color: rgba(139, 92, 246, 0.5); }
        .plan-card.popular { border-color: #a855f7; position: relative; }
        .popular-badge {
            position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
            background: #a855f7; padding: 4px 16px; border-radius: 20px;
            font-size: 12px; font-weight: 600;
        }
        .plan-name { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
        .plan-price { font-size: 48px; font-weight: 700; margin: 20px 0; }
        .plan-price span { font-size: 16px; color: rgba(255,255,255,0.6); }
        .plan-features { list-style: none; margin: 24px 0; text-align: left; }
        .plan-features li { padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); color: rgba(255,255,255,0.8); }
        .plan-features li::before { content: "✓ "; color: #00d26a; font-weight: bold; }
        .plan-btn {
            width: 100%; padding: 14px; border: none; border-radius: 10px;
            font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s;
        }
        .plan-btn.primary {
            background: linear-gradient(135deg, #a855f7, #6366f1); color: #fff;
        }
        .plan-btn.secondary {
            background: rgba(255,255,255,0.1); color: #fff;
        }
        .plan-btn:hover { transform: scale(1.02); }
        .back-link { text-align: center; margin-top: 40px; }
        .back-link a { color: #a855f7; text-decoration: none; }
        
        /* Modal */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); align-items: center; justify-content: center; z-index: 1000; }
        .modal.active { display: flex; }
        .modal-content {
            background: rgba(30, 30, 50, 0.95); padding: 30px; border-radius: 20px;
            width: 100%; max-width: 450px; border: 1px solid rgba(139, 92, 246, 0.3);
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h3 { font-size: 20px; }
        .modal-close { background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 8px; color: rgba(255,255,255,0.8); font-size: 14px; }
        .form-group input {
            width: 100%; padding: 12px 16px; background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
            color: #fff; font-size: 16px; outline: none;
        }
        .upi-box {
            background: rgba(168, 85, 247, 0.1); padding: 20px; border-radius: 12px;
            text-align: center; margin: 20px 0;
        }
        .upi-id { font-size: 18px; font-weight: 600; color: #a855f7; margin: 10px 0; }
        .upi-btn {
            display: inline-block; padding: 14px 30px;
            background: linear-gradient(135deg, #00d26a, #00a854);
            border-radius: 10px; color: #fff; font-weight: 600;
            text-decoration: none; margin-top: 10px;
        }
        @media (max-width: 768px) { .plans-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💎 Upgrade Your Trading</h1>
            <p>Choose a plan that fits your trading needs</p>
        </div>
        
        <div class="wallet-card">
            <div>
                <div class="wallet-label">💰 Wallet Balance</div>
                <div class="wallet-balance" id="walletBalance">₹0</div>
            </div>
            <button class="add-money-btn" onclick="openAddMoneyModal()">+ Add Money</button>
        </div>
        
        <div class="plans-grid" id="plansGrid">
            <!-- Plans will be loaded here -->
        </div>
        
        <div class="back-link">
            <a href="/">← Back to Dashboard</a>
        </div>
    </div>
    
    <!-- Add Money Modal -->
    <div class="modal" id="addMoneyModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>💳 Add Money to Wallet</h3>
                <button class="modal-close" onclick="closeAddMoneyModal()">&times;</button>
            </div>
            
            <div class="form-group">
                <label>Amount (₹)</label>
                <input type="number" id="paymentAmount" placeholder="Enter amount" min="100">
            </div>
            <div class="form-group">
                <label>Your Name</label>
                <input type="text" id="paymentName" placeholder="Name for payment reference">
            </div>
            <div class="form-group">
                <label>Phone Number</label>
                <input type="tel" id="paymentPhone" placeholder="For payment confirmation">
            </div>
            
            <div class="upi-box" id="upiBox" style="display: none;">
                <p>📱 Scan QR or Pay via UPI</p>
                <div class="upi-id" id="upiIdDisplay">adityagen.lko@oksbi</div>
                <p style="color: rgba(255,255,255,0.6); font-size: 14px;">Pay to: Aditya Verma</p>
                <a href="#" id="upiLink" class="upi-btn">Open UPI App to Pay</a>
                <p style="margin-top: 15px; font-size: 12px; color: rgba(255,255,255,0.5);">
                    After payment, it will be verified by admin and credited to your wallet.
                </p>
            </div>
            
            <button class="plan-btn primary" onclick="createPaymentRequest()" id="proceedBtn">
                Proceed to Pay
            </button>
        </div>
    </div>
    
    <script>
        // Load user data
        async function loadData() {
            const userRes = await fetch('/api/auth/me');
            const user = await userRes.json();
            document.getElementById('walletBalance').textContent = '₹' + (user.wallet_balance || 0).toLocaleString();
            document.getElementById('paymentName').value = user.name || '';
            document.getElementById('paymentPhone').value = user.phone || '';
            
            // Load plans
            const plansRes = await fetch('/api/subscription/plans');
            const plans = await plansRes.json();
            
            const plansHtml = Object.entries(plans).map(([key, plan]) => `
                <div class="plan-card ${key === 'premium' ? 'popular' : ''}">
                    ${key === 'premium' ? '<div class="popular-badge">MOST POPULAR</div>' : ''}
                    <div class="plan-name">${plan.name}</div>
                    <div class="plan-price">₹${plan.price}<span>/month</span></div>
                    <ul class="plan-features">
                        ${plan.features.map(f => `<li>${f}</li>`).join('')}
                    </ul>
                    <button class="plan-btn ${key === 'premium' ? 'primary' : 'secondary'}"
                            onclick="purchasePlan('${key}', ${plan.price})"
                            ${plan.price === 0 ? 'disabled' : ''}>
                        ${plan.price === 0 ? 'Current Plan' : 'Subscribe Now'}
                    </button>
                </div>
            `).join('');
            
            document.getElementById('plansGrid').innerHTML = plansHtml;
        }
        
        function openAddMoneyModal() {
            document.getElementById('addMoneyModal').classList.add('active');
            document.getElementById('upiBox').style.display = 'none';
            document.getElementById('proceedBtn').style.display = 'block';
        }
        
        function closeAddMoneyModal() {
            document.getElementById('addMoneyModal').classList.remove('active');
        }
        
        async function createPaymentRequest() {
            const amount = document.getElementById('paymentAmount').value;
            const name = document.getElementById('paymentName').value;
            const phone = document.getElementById('paymentPhone').value;
            
            if (!amount || amount < 100) {
                alert('Please enter amount (minimum ₹100)');
                return;
            }
            
            const res = await fetch('/api/payment/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ amount, name, phone })
            });
            
            const data = await res.json();
            if (data.payment) {
                document.getElementById('upiLink').href = data.upi_link;
                document.getElementById('upiIdDisplay').textContent = data.upi_id;
                document.getElementById('upiBox').style.display = 'block';
                document.getElementById('proceedBtn').style.display = 'none';
            }
        }
        
        async function purchasePlan(plan, price) {
            const userRes = await fetch('/api/auth/me');
            const user = await userRes.json();
            
            if (user.wallet_balance < price) {
                alert(`Insufficient balance! You need ₹${price} but have ₹${user.wallet_balance}. Please add money first.`);
                openAddMoneyModal();
                return;
            }
            
            if (confirm(`Purchase ${plan} plan for ₹${price}?`)) {
                const res = await fetch('/api/subscription/purchase', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ plan })
                });
                
                const data = await res.json();
                if (data.success) {
                    alert('Subscription activated! Enjoy your premium features.');
                    window.location.href = '/';
                } else {
                    alert(data.error || 'Failed to purchase');
                }
            }
        }
        
        loadData();
    </script>
</body>
</html>
'''


@pages_bp.route('/wallet')
@login_required
def wallet_page():
    """User wallet page."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wallet - AI Trading System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh; color: #fff; padding: 40px 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        .card {
            background: rgba(30, 30, 50, 0.9); border-radius: 20px; padding: 30px;
            border: 1px solid rgba(139, 92, 246, 0.3); margin-bottom: 24px;
        }
        .balance-card { text-align: center; }
        .balance-label { color: rgba(255,255,255,0.6); font-size: 14px; }
        .balance-amount { font-size: 48px; font-weight: 700; color: #00d26a; margin: 10px 0; }
        .btn-group { display: flex; gap: 16px; justify-content: center; margin-top: 20px; }
        .btn {
            padding: 14px 30px; border: none; border-radius: 10px;
            font-size: 16px; font-weight: 600; cursor: pointer; text-decoration: none;
        }
        .btn-primary { background: linear-gradient(135deg, #a855f7, #6366f1); color: #fff; }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #fff; }
        .section-title { font-size: 18px; margin-bottom: 16px; }
        .transaction {
            display: flex; justify-content: space-between; padding: 16px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .transaction:last-child { border-bottom: none; }
        .tx-type { font-size: 14px; color: rgba(255,255,255,0.6); }
        .tx-amount { font-weight: 600; }
        .tx-amount.credit { color: #00d26a; }
        .tx-amount.debit { color: #ff4757; }
        .back-link { text-align: center; margin-top: 20px; }
        .back-link a { color: #a855f7; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card balance-card">
            <div class="balance-label">💰 Available Balance</div>
            <div class="balance-amount" id="balance">₹0</div>
            <div class="btn-group">
                <a href="/subscribe" class="btn btn-primary">+ Add Money</a>
                <a href="/subscribe" class="btn btn-secondary">Subscribe</a>
            </div>
        </div>
        
        <div class="card">
            <h3 class="section-title">📋 Recent Transactions</h3>
            <div id="transactions">
                <p style="text-align: center; color: rgba(255,255,255,0.5); padding: 20px;">
                    No transactions yet
                </p>
            </div>
        </div>
        
        <div class="back-link">
            <a href="/">← Back to Dashboard</a>
        </div>
    </div>
    
    <script>
        async function loadWallet() {
            const res = await fetch('/api/wallet/balance');
            const data = await res.json();
            
            document.getElementById('balance').textContent = '₹' + (data.balance || 0).toLocaleString();
            
            if (data.transactions && data.transactions.length > 0) {
                document.getElementById('transactions').innerHTML = data.transactions.map(tx => `
                    <div class="transaction">
                        <div>
                            <div>${tx.description || (tx.type === 'credit' ? 'Money Added' : 'Subscription')}</div>
                            <div class="tx-type">${new Date(tx.timestamp).toLocaleString()}</div>
                        </div>
                        <div class="tx-amount ${tx.type}">
                            ${tx.type === 'credit' ? '+' : '-'}₹${tx.amount.toLocaleString()}
                        </div>
                    </div>
                `).join('');
            }
        }
        loadWallet();
    </script>
</body>
</html>
'''


@pages_bp.route('/admin')
@admin_required
def admin_page():
    """Admin panel page."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - AI Trading System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh; color: #fff; padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 0; margin-bottom: 30px; border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #ff4757, #ff6b81);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .tabs { display: flex; gap: 8px; margin-bottom: 30px; }
        .tab {
            padding: 12px 24px; background: rgba(255,255,255,0.05);
            border: none; border-radius: 10px; color: #fff;
            cursor: pointer; font-size: 14px; font-weight: 500;
        }
        .tab.active { background: linear-gradient(135deg, #a855f7, #6366f1); }
        .card {
            background: rgba(30, 30, 50, 0.9); border-radius: 16px; padding: 24px;
            border: 1px solid rgba(139, 92, 246, 0.3); margin-bottom: 20px;
        }
        .card-title { font-size: 18px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }
        th { color: rgba(255,255,255,0.6); font-weight: 500; font-size: 12px; text-transform: uppercase; }
        .badge {
            padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;
        }
        .badge-pending { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
        .badge-approved { background: rgba(0, 210, 106, 0.2); color: #00d26a; }
        .badge-rejected { background: rgba(255, 71, 87, 0.2); color: #ff4757; }
        .btn {
            padding: 8px 16px; border: none; border-radius: 8px;
            font-size: 12px; font-weight: 600; cursor: pointer; margin-right: 8px;
        }
        .btn-approve { background: #00d26a; color: #fff; }
        .btn-reject { background: #ff4757; color: #fff; }
        .btn-assign { background: #a855f7; color: #fff; }
        .section { display: none; }
        .section.active { display: block; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 30px; }
        .stat-card {
            background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px; text-align: center;
        }
        .stat-value { font-size: 32px; font-weight: 700; color: #a855f7; }
        .stat-label { font-size: 12px; color: rgba(255,255,255,0.6); margin-top: 4px; }
        .back-link a { color: #a855f7; text-decoration: none; }
        
        /* Modal */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); align-items: center; justify-content: center; z-index: 1000; }
        .modal.active { display: flex; }
        .modal-content { background: rgba(30, 30, 50, 0.95); padding: 30px; border-radius: 20px; width: 100%; max-width: 400px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-close { background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 8px; font-size: 14px; color: rgba(255,255,255,0.8); }
        .form-group input, .form-group select {
            width: 100%; padding: 12px; background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
            color: #fff; font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Admin Panel</h1>
            <div class="back-link"><a href="/">← Back to Dashboard</a></div>
        </div>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card"><div class="stat-value" id="totalUsers">0</div><div class="stat-label">Total Users</div></div>
            <div class="stat-card"><div class="stat-value" id="pendingApprovals">0</div><div class="stat-label">Pending Approvals</div></div>
            <div class="stat-card"><div class="stat-value" id="pendingPayments">0</div><div class="stat-label">Pending Payments</div></div>
            <div class="stat-card"><div class="stat-value" id="activeSubscriptions">0</div><div class="stat-label">Active Subscriptions</div></div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showSection('users')">👥 Users</button>
            <button class="tab" onclick="showSection('payments')">💳 Payments</button>
            <button class="tab" onclick="showSection('subscriptions')">📦 Subscriptions</button>
        </div>
        
        <!-- Users Section -->
        <div id="users" class="section active">
            <div class="card">
                <h3 class="card-title">👥 All Users</h3>
                <table>
                    <thead>
                        <tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th>Subscription</th><th>Wallet</th><th>Actions</th></tr>
                    </thead>
                    <tbody id="usersTable"></tbody>
                </table>
            </div>
        </div>
        
        <!-- Payments Section -->
        <div id="payments" class="section">
            <div class="card">
                <h3 class="card-title">💳 Pending Payments</h3>
                <table>
                    <thead>
                        <tr><th>ID</th><th>User</th><th>Amount</th><th>Name</th><th>Phone</th><th>Date</th><th>Actions</th></tr>
                    </thead>
                    <tbody id="paymentsTable"></tbody>
                </table>
            </div>
        </div>
        
        <!-- Subscriptions Section -->
        <div id="subscriptions" class="section">
            <div class="card">
                <h3 class="card-title">📦 Assign Subscription</h3>
                <p style="color: rgba(255,255,255,0.6); margin-bottom: 20px;">
                    Manually assign subscription to any user
                </p>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 16px; align-items: end;">
                    <div class="form-group" style="margin: 0;">
                        <label>User Email</label>
                        <input type="email" id="assignEmail" placeholder="user@example.com">
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>Plan</label>
                        <select id="assignPlan">
                            <option value="premium">Premium (₹499)</option>
                            <option value="pro">Pro (₹999)</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>Days</label>
                        <input type="number" id="assignDays" value="30" min="1">
                    </div>
                    <button class="btn btn-assign" onclick="assignSubscription()">Assign</button>
                </div>
            </div>
            
            <div class="card">
                <h3 class="card-title">💰 Add Wallet Balance</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 16px; align-items: end;">
                    <div class="form-group" style="margin: 0;">
                        <label>User Email</label>
                        <input type="email" id="walletEmail" placeholder="user@example.com">
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>Amount (₹)</label>
                        <input type="number" id="walletAmount" placeholder="500" min="1">
                    </div>
                    <button class="btn btn-approve" onclick="addWalletBalance()">Add Balance</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let allUsers = [];
        
        async function loadData() {
            // Load users
            const usersRes = await fetch('/api/admin/users');
            allUsers = await usersRes.json();
            
            // Load pending payments
            const paymentsRes = await fetch('/api/admin/pending_payments');
            const payments = await paymentsRes.json();
            
            // Update stats
            document.getElementById('totalUsers').textContent = allUsers.length;
            document.getElementById('pendingApprovals').textContent = allUsers.filter(u => !u.is_approved).length;
            document.getElementById('pendingPayments').textContent = payments.length;
            document.getElementById('activeSubscriptions').textContent = allUsers.filter(u => u.subscription !== 'free').length;
            
            // Render users table
            document.getElementById('usersTable').innerHTML = allUsers.map(user => `
                <tr>
                    <td>${user.name}</td>
                    <td>${user.email}</td>
                    <td>${user.phone || '-'}</td>
                    <td>
                        <span class="badge ${user.is_approved ? 'badge-approved' : 'badge-pending'}">
                            ${user.is_approved ? 'Approved' : 'Pending'}
                        </span>
                    </td>
                    <td>${user.subscription}</td>
                    <td>₹${(user.wallet_balance || 0).toLocaleString()}</td>
                    <td>
                        ${!user.is_approved ? `<button class="btn btn-approve" onclick="approveUser('${user.email}')">Approve</button>` : ''}
                    </td>
                </tr>
            `).join('');
            
            // Render payments table
            document.getElementById('paymentsTable').innerHTML = payments.length > 0 ? payments.map(p => `
                <tr>
                    <td>${p.id}</td>
                    <td>${p.email}</td>
                    <td>₹${p.amount.toLocaleString()}</td>
                    <td>${p.name}</td>
                    <td>${p.phone}</td>
                    <td>${new Date(p.created_at).toLocaleString()}</td>
                    <td>
                        <button class="btn btn-approve" onclick="approvePayment('${p.id}')">Approve</button>
                        <button class="btn btn-reject" onclick="rejectPayment('${p.id}')">Reject</button>
                    </td>
                </tr>
            `).join('') : '<tr><td colspan="7" style="text-align: center; padding: 30px; color: rgba(255,255,255,0.5);">No pending payments</td></tr>';
        }
        
        function showSection(name) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(name).classList.add('active');
            event.target.classList.add('active');
        }
        
        async function approveUser(email) {
            await fetch(`/api/admin/approve/${email}`, { method: 'POST' });
            loadData();
        }
        
        async function approvePayment(id) {
            await fetch(`/api/admin/approve_payment/${id}`, { method: 'POST' });
            alert('Payment approved and wallet credited!');
            loadData();
        }
        
        async function rejectPayment(id) {
            if (confirm('Reject this payment?')) {
                await fetch(`/api/admin/reject_payment/${id}`, { method: 'POST' });
                loadData();
            }
        }
        
        async function assignSubscription() {
            const email = document.getElementById('assignEmail').value;
            const plan = document.getElementById('assignPlan').value;
            const days = document.getElementById('assignDays').value;
            
            if (!email) { alert('Enter email'); return; }
            
            await fetch('/api/admin/assign_subscription', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email, plan, days: parseInt(days) })
            });
            
            alert('Subscription assigned!');
            document.getElementById('assignEmail').value = '';
            loadData();
        }
        
        async function addWalletBalance() {
            const email = document.getElementById('walletEmail').value;
            const amount = document.getElementById('walletAmount').value;
            
            if (!email || !amount) { alert('Enter email and amount'); return; }
            
            await fetch('/api/admin/add_wallet_balance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email, amount: parseFloat(amount) })
            });
            
            alert('Balance added!');
            document.getElementById('walletEmail').value = '';
            document.getElementById('walletAmount').value = '';
            loadData();
        }
        
        loadData();
    </script>
</body>
</html>
'''


@pages_bp.route('/payment-status')
def payment_status_page():
    """Payment status page after UPI payment."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Status - AI Trading System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh; display: flex; align-items: center;
            justify-content: center; color: #fff; padding: 20px;
        }
        .card {
            background: rgba(30, 30, 50, 0.9); padding: 40px;
            border-radius: 20px; text-align: center; max-width: 500px;
            border: 1px solid rgba(139, 92, 246, 0.3);
        }
        .icon { font-size: 64px; margin-bottom: 20px; }
        h1 { font-size: 24px; margin-bottom: 12px; }
        p { color: rgba(255,255,255,0.7); margin-bottom: 20px; line-height: 1.6; }
        .btn {
            display: inline-block; padding: 14px 30px;
            background: linear-gradient(135deg, #a855f7, #6366f1);
            border: none; border-radius: 10px; color: #fff;
            font-size: 16px; font-weight: 600; text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">⏳</div>
        <h1>Payment Verification Pending</h1>
        <p>
            Thank you for your payment! Our admin will verify your payment 
            and credit the amount to your wallet within 24 hours.
        </p>
        <p>
            You will be able to use your wallet balance to purchase 
            subscriptions once the payment is approved.
        </p>
        <a href="/wallet" class="btn">Check Wallet Status</a>
    </div>
</body>
</html>
'''
