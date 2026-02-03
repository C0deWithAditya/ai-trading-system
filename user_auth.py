"""
User Authentication and Management System for Trading AI Platform.
Handles user registration, login, and admin functions.
"""

import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path
import pytz

# Data files
USERS_FILE = "data/users.json"
SESSIONS_FILE = "data/sessions.json"
WALLETS_FILE = "data/wallets.json"
PAYMENTS_FILE = "data/payments.json"
SUBSCRIPTIONS_FILE = "data/subscriptions.json"

# Ensure data directory exists
Path("data").mkdir(exist_ok=True)

# Subscription Plans
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "duration_days": 365,
        "features": ["Basic dashboard", "Limited signals (5/day)", "Delayed alerts"],
    },
    "premium": {
        "name": "Premium",
        "price": 499,
        "duration_days": 30,
        "features": ["Full dashboard", "Unlimited signals", "Real-time Telegram alerts", "AI Analysis"],
    },
    "pro": {
        "name": "Pro",
        "price": 999,
        "duration_days": 30,
        "features": ["Everything in Premium", "Priority signals", "Virtual trading P&L", "Hourly reports", "Support"],
    },
}


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


class UserManager:
    """Manages user accounts and authentication."""
    
    def __init__(self):
        self.users: Dict = {}
        self.sessions: Dict = {}
        self.load()
    
    def load(self):
        """Load users and sessions from files."""
        try:
            if Path(USERS_FILE).exists():
                with open(USERS_FILE, 'r') as f:
                    self.users = json.load(f)
            if Path(SESSIONS_FILE).exists():
                with open(SESSIONS_FILE, 'r') as f:
                    self.sessions = json.load(f)
        except Exception as e:
            print(f"Error loading user data: {e}")
    
    def save(self):
        """Save users and sessions to files."""
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump(self.users, f, indent=2)
            with open(SESSIONS_FILE, 'w') as f:
                json.dump(self.sessions, f, indent=2)
        except Exception as e:
            print(f"Error saving user data: {e}")
    
    def create_user(self, email: str, password: str, name: str, phone: str = "") -> Dict:
        """Create a new user account."""
        if email in self.users:
            return {"success": False, "error": "Email already registered"}
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        user = {
            "email": email,
            "password": hash_password(password),
            "name": name,
            "phone": phone,
            "is_admin": False,
            "is_approved": False,  # Needs admin approval
            "subscription": "free",
            "subscription_expires": None,
            "created_at": now.isoformat(),
            "last_login": None,
        }
        
        self.users[email] = user
        self.save()
        
        # Initialize wallet
        wallet_mgr = WalletManager()
        wallet_mgr.create_wallet(email)
        
        return {"success": True, "user": user}
    
    def login(self, email: str, password: str) -> Dict:
        """Authenticate user and create session."""
        if email not in self.users:
            return {"success": False, "error": "Invalid email or password"}
        
        user = self.users[email]
        if user["password"] != hash_password(password):
            return {"success": False, "error": "Invalid email or password"}
        
        if not user["is_approved"] and not user["is_admin"]:
            return {"success": False, "error": "Account pending approval. Please wait for admin approval."}
        
        # Create session
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        token = generate_session_token()
        self.sessions[token] = {
            "email": email,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        }
        
        user["last_login"] = now.isoformat()
        self.save()
        
        return {"success": True, "token": token, "user": user}
    
    def get_user_from_token(self, token: str) -> Optional[Dict]:
        """Get user from session token."""
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        ist = pytz.timezone('Asia/Kolkata')
        expires = datetime.fromisoformat(session["expires_at"])
        
        if datetime.now(ist) > expires:
            del self.sessions[token]
            self.save()
            return None
        
        email = session["email"]
        return self.users.get(email)
    
    def logout(self, token: str) -> bool:
        """End user session."""
        if token in self.sessions:
            del self.sessions[token]
            self.save()
            return True
        return False
    
    def get_all_users(self) -> List[Dict]:
        """Get all users (for admin)."""
        return [
            {k: v for k, v in user.items() if k != "password"}
            for user in self.users.values()
        ]
    
    def approve_user(self, email: str) -> bool:
        """Approve a user account."""
        if email in self.users:
            self.users[email]["is_approved"] = True
            self.save()
            return True
        return False
    
    def update_subscription(self, email: str, plan: str, days: int = None) -> bool:
        """Update user subscription."""
        if email not in self.users:
            return False
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        if days is None:
            days = SUBSCRIPTION_PLANS.get(plan, {}).get("duration_days", 30)
        
        self.users[email]["subscription"] = plan
        self.users[email]["subscription_expires"] = (now + timedelta(days=days)).isoformat()
        self.save()
        return True
    
    def create_admin(self, email: str, password: str, name: str):
        """Create admin account if not exists."""
        if email not in self.users:
            self.create_user(email, password, name)
        
        self.users[email]["is_admin"] = True
        self.users[email]["is_approved"] = True
        self.users[email]["subscription"] = "pro"
        self.save()


class WalletManager:
    """Manages user wallets and transactions."""
    
    def __init__(self):
        self.wallets: Dict = {}
        self.load()
    
    def load(self):
        try:
            if Path(WALLETS_FILE).exists():
                with open(WALLETS_FILE, 'r') as f:
                    self.wallets = json.load(f)
        except Exception as e:
            print(f"Error loading wallets: {e}")
    
    def save(self):
        try:
            with open(WALLETS_FILE, 'w') as f:
                json.dump(self.wallets, f, indent=2)
        except Exception as e:
            print(f"Error saving wallets: {e}")
    
    def create_wallet(self, email: str):
        """Create wallet for user."""
        if email not in self.wallets:
            self.wallets[email] = {
                "balance": 0,
                "transactions": [],
            }
            self.save()
    
    def get_balance(self, email: str) -> float:
        """Get wallet balance."""
        if email not in self.wallets:
            self.create_wallet(email)
        return self.wallets[email]["balance"]
    
    def add_balance(self, email: str, amount: float, description: str = ""):
        """Add money to wallet (admin approved payment)."""
        if email not in self.wallets:
            self.create_wallet(email)
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        self.wallets[email]["balance"] += amount
        self.wallets[email]["transactions"].append({
            "type": "credit",
            "amount": amount,
            "description": description,
            "timestamp": now.isoformat(),
        })
        self.save()
    
    def deduct_balance(self, email: str, amount: float, description: str = "") -> bool:
        """Deduct money for subscription purchase."""
        if email not in self.wallets:
            return False
        
        if self.wallets[email]["balance"] < amount:
            return False
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        self.wallets[email]["balance"] -= amount
        self.wallets[email]["transactions"].append({
            "type": "debit",
            "amount": amount,
            "description": description,
            "timestamp": now.isoformat(),
        })
        self.save()
        return True
    
    def get_transactions(self, email: str) -> List[Dict]:
        """Get transaction history."""
        if email not in self.wallets:
            return []
        return self.wallets[email].get("transactions", [])[-20:][::-1]


class PaymentManager:
    """Manages payment requests and approvals."""
    
    # UPI Details
    UPI_ID = "adityagen.lko@oksbi"
    UPI_NAME = "Aditya Verma"
    
    def __init__(self):
        self.payments: List[Dict] = []
        self.load()
    
    def load(self):
        try:
            if Path(PAYMENTS_FILE).exists():
                with open(PAYMENTS_FILE, 'r') as f:
                    self.payments = json.load(f)
        except Exception as e:
            print(f"Error loading payments: {e}")
    
    def save(self):
        try:
            with open(PAYMENTS_FILE, 'w') as f:
                json.dump(self.payments, f, indent=2)
        except Exception as e:
            print(f"Error saving payments: {e}")
    
    def create_payment_request(self, email: str, amount: float, name: str, phone: str) -> Dict:
        """Create a new payment request."""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        payment_id = f"PAY{len(self.payments) + 1001}"
        
        payment = {
            "id": payment_id,
            "email": email,
            "amount": amount,
            "name": name,
            "phone": phone,
            "status": "pending",  # pending, approved, rejected
            "created_at": now.isoformat(),
            "approved_at": None,
            "approved_by": None,
        }
        
        self.payments.append(payment)
        self.save()
        
        return payment
    
    def get_upi_link(self, amount: float, payment_id: str) -> str:
        """Generate UPI payment link."""
        return f"upi://pay?pa={self.UPI_ID}&pn={self.UPI_NAME}&am={amount}&tn=TradingAI-{payment_id}&cu=INR"
    
    def approve_payment(self, payment_id: str, admin_email: str) -> bool:
        """Admin approves a payment."""
        for payment in self.payments:
            if payment["id"] == payment_id and payment["status"] == "pending":
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.now(ist)
                
                payment["status"] = "approved"
                payment["approved_at"] = now.isoformat()
                payment["approved_by"] = admin_email
                self.save()
                
                # Add to wallet
                wallet_mgr = WalletManager()
                wallet_mgr.add_balance(
                    payment["email"], 
                    payment["amount"], 
                    f"Payment {payment_id} approved"
                )
                
                return True
        return False
    
    def reject_payment(self, payment_id: str, admin_email: str) -> bool:
        """Admin rejects a payment."""
        for payment in self.payments:
            if payment["id"] == payment_id and payment["status"] == "pending":
                payment["status"] = "rejected"
                self.save()
                return True
        return False
    
    def get_pending_payments(self) -> List[Dict]:
        """Get all pending payments (for admin)."""
        return [p for p in self.payments if p["status"] == "pending"]
    
    def get_user_payments(self, email: str) -> List[Dict]:
        """Get payments for a user."""
        return [p for p in self.payments if p["email"] == email][-10:][::-1]


# Global instances
_user_manager = None
_wallet_manager = None
_payment_manager = None


def get_user_manager() -> UserManager:
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager


def get_wallet_manager() -> WalletManager:
    global _wallet_manager
    if _wallet_manager is None:
        _wallet_manager = WalletManager()
    return _wallet_manager


def get_payment_manager() -> PaymentManager:
    global _payment_manager
    if _payment_manager is None:
        _payment_manager = PaymentManager()
    return _payment_manager


# Initialize admin account
def init_admin():
    """Create default admin account."""
    user_mgr = get_user_manager()
    user_mgr.create_admin("admin@trading.ai", "admin123", "Admin")
    print("Admin account created: admin@trading.ai / admin123")
