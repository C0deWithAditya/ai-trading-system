"""
Web Dashboard for the Multi-Index F&O Trading System.
Provides a real-time view of signals, market data, and usage stats for multiple indices.
Now includes interactive charts with AI Signal overlays.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
import pytz
from flask import Flask, render_template_string, jsonify, Response, request
import queue

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from usage_monitor import get_usage_monitor
from index_config import get_index_manager, AVAILABLE_INDICES

app = Flask(__name__)

# Register authentication blueprints
try:
    from auth_routes import auth_bp, get_current_user, login_required
    from pages import pages_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    AUTH_ENABLED = True
except ImportError as e:
    print(f"Auth not enabled: {e}")
    AUTH_ENABLED = False
    def get_current_user(): return {"is_admin": True, "subscription": "pro"}
    def login_required(f): return f

# Global state for dashboard
dashboard_state = {
    "signals": [],
    "market_data": {},  # Now keyed by index name
    "system_status": "Stopped",
    "last_signal": None,
}

# Initialize market data for all indices
for index_name in AVAILABLE_INDICES.keys():
    dashboard_state["market_data"][index_name] = {
        "spot_price": 0,
        "pcr": 0,
        "vwap": 0,
        "support": 0,
        "resistance": 0,
        "candles": [],  # Store candle history
        "last_update": None,
    }

# Queue for real-time updates
update_queue = queue.Queue()


def add_signal(signal_data: dict):
    """Add a new signal to the dashboard."""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    signal_data["timestamp"] = now.strftime("%H:%M:%S")
    # Add timestamp for chart marker (approximate)
    signal_data["chart_time"] = int(now.timestamp())
    
    dashboard_state["signals"].insert(0, signal_data)
    dashboard_state["signals"] = dashboard_state["signals"][:100]  # Keep last 100
    dashboard_state["last_signal"] = signal_data
    update_queue.put({"type": "signal", "data": signal_data})


def update_market_data(index_name: str, data: dict):
    """Update market data for a specific index."""
    if index_name not in dashboard_state["market_data"]:
        dashboard_state["market_data"][index_name] = {
            "spot_price": 0, "pcr": 0, "vwap": 0, 
            "support": 0, "resistance": 0, "candles": []
        }
    
    # Store previous candles if new ones aren't provided
    current_candles = dashboard_state["market_data"][index_name].get("candles", [])
    new_candles = data.get("candles", [])
    
    # Update state
    dashboard_state["market_data"][index_name].update(data)
    
    # If no new candles, keep old ones. If new candles, replace or append.
    # For simplicity, we replace if provided, as the backend sends the full list or extensive history
    if not new_candles:
        dashboard_state["market_data"][index_name]["candles"] = current_candles
        
    dashboard_state["market_data"][index_name]["last_update"] = datetime.now().strftime("%H:%M:%S")
    
    # Prepare data for frontend (exclude heavy candle data from regular updates to save bandwidth)
    frontend_data = dashboard_state["market_data"][index_name].copy()
    del frontend_data["candles"]
    
    update_queue.put({"type": "market", "index": index_name, "data": frontend_data})


def set_system_status(status: str):
    """Set system status."""
    dashboard_state["system_status"] = status
    update_queue.put({"type": "status", "data": status})


# HTML Template with TradingView Charts
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 AI Trading Dashboard - Live Charts</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-card: #16213e;
            --accent-green: #00d26a;
            --accent-red: #ff4757;
            --accent-blue: #5352ed;
            --accent-purple: #a855f7;
            --accent-orange: #ff9f43;
            --accent-cyan: #00d2d3;
            --text-primary: #ffffff;
            --text-secondary: #a0a0b0;
            --border-color: #2d2d44;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 30px;
        }
        
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo h1 {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-right { display: flex; align-items: center; gap: 16px; }
        
        .status-badge {
            display: flex; align-items: center; gap: 8px;
            padding: 8px 16px; border-radius: 20px;
            font-size: 14px; font-weight: 500;
        }
        
        .status-running {
            background: rgba(0, 210, 106, 0.15); color: var(--accent-green);
            border: 1px solid var(--accent-green);
        }
        .status-stopped {
            background: rgba(255, 71, 87, 0.15); color: var(--accent-red);
            border: 1px solid var(--accent-red);
        }
        
        .pulse { width: 8px; height: 8px; border-radius: 50%; animation: pulse 2s infinite; }
        .pulse-green { background: var(--accent-green); }
        .pulse-red { background: var(--accent-red); }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }
        
        /* User Menu */
        .user-menu { position: relative; }
        .user-btn {
            display: flex; align-items: center; gap: 10px;
            padding: 8px 16px; background: var(--bg-secondary);
            border: 1px solid var(--border-color); border-radius: 12px;
            cursor: pointer; font-size: 14px; color: var(--text-primary);
        }
        .user-btn:hover { border-color: var(--accent-purple); }
        .user-avatar {
            width: 32px; height: 32px; border-radius: 50%;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            display: flex; align-items: center; justify-content: center;
            font-weight: 600; font-size: 14px;
        }
        .user-dropdown {
            position: absolute; top: 100%; right: 0; margin-top: 8px;
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 12px; min-width: 220px; display: none; z-index: 100;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .user-dropdown.active { display: block; }
        .user-dropdown-item {
            display: flex; align-items: center; gap: 10px;
            padding: 12px 16px; color: var(--text-primary);
            text-decoration: none; transition: background 0.2s;
        }
        .user-dropdown-item:hover { background: rgba(255,255,255,0.05); }
        .user-dropdown-item.danger { color: var(--accent-red); }
        .user-info { padding: 16px; border-bottom: 1px solid var(--border-color); }
        .user-email { font-size: 12px; color: var(--text-secondary); }
        .wallet-badge { 
            background: rgba(0, 210, 106, 0.15); color: var(--accent-green);
            padding: 2px 8px; border-radius: 8px; font-size: 12px; font-weight: 600;
        }
        .sub-badge {
            padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 600; text-transform: uppercase;
        }
        .sub-free { background: rgba(255,255,255,0.1); color: var(--text-secondary); }
        .sub-premium { background: rgba(168, 85, 247, 0.2); color: #a855f7; }
        .sub-pro { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
        
        /* Index Toggles */
        .index-toggles { display: flex; gap: 8px; flex-wrap: wrap; }
        .index-toggle {
            display: flex; align-items: center; gap: 8px;
            padding: 8px 16px; border-radius: 12px;
            cursor: pointer; transition: all 0.2s;
            border: 1px solid var(--border-color); background: var(--bg-secondary);
            font-size: 13px;
        }
        .index-toggle:hover { border-color: var(--accent-purple); }
        .index-toggle.active { background: rgba(168, 85, 247, 0.15); border-color: var(--accent-purple); }
        .index-toggle .toggle-switch {
            width: 36px; height: 20px; border-radius: 10px;
            background: var(--border-color); position: relative; transition: background 0.2s;
        }
        .index-toggle.active .toggle-switch { background: var(--accent-purple); }
        .index-toggle .toggle-switch::after {
            content: ''; position: absolute; width: 16px; height: 16px;
            border-radius: 50%; background: white; top: 2px; left: 2px; transition: left 0.2s;
        }
        .index-toggle.active .toggle-switch::after { left: 18px; }
        
        /* Grid Layout */
        .dashboard-grid {
            display: grid; grid-template-columns: repeat(12, 1fr); gap: 20px;
        }
        
        /* Cards */
        .card {
            background: var(--bg-card); border-radius: 16px; padding: 24px;
            border: 1px solid var(--border-color); transition: transform 0.2s, box-shadow 0.2s;
        }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .card-title {
            font-size: 14px; font-weight: 600; color: var(--text-secondary);
            text-transform: uppercase; letter-spacing: 1px;
        }
        
        /* Chart Section */
        .chart-section { grid-column: span 12; height: 500px; display: flex; flex-direction: column; }
        .chart-controls { display: flex; gap: 10px; margin-bottom: 10px; }
        .chart-tab {
            padding: 6px 12px; border-radius: 8px; background: var(--bg-secondary);
            border: 1px solid var(--border-color); color: var(--text-secondary);
            cursor: pointer; font-size: 12px;
        }
        .chart-tab.active {
            background: var(--accent-blue); color: white; border-color: var(--accent-blue);
        }
        #chart-container { flex: 1; width: 100%; border-radius: 8px; overflow: hidden; }
        
        /* Index Cards */
        .indices-section { grid-column: span 12; }
        .indices-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .index-card {
            background: var(--bg-card); border-radius: 16px; padding: 20px;
            border: 1px solid var(--border-color);
        }
        .index-card-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border-color);
        }
        .index-name { font-size: 18px; font-weight: 700; }
        .index-price { font-size: 24px; font-weight: 700; }
        .index-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .mini-stat { text-align: center; padding: 10px; background: var(--bg-secondary); border-radius: 8px; }
        .mini-stat-label { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; }
        .mini-stat-value { font-size: 16px; font-weight: 600; margin-top: 4px; }
        .mini-stat-value.green { color: var(--accent-green); }
        .mini-stat-value.red { color: var(--accent-red); }
        
        /* Stats & Signals */
        .signals-panel { grid-column: span 8; }
        .usage-stats { grid-column: span 4; }
        .usage-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .usage-item { padding: 16px; background: var(--bg-secondary); border-radius: 12px; text-align: center; }
        .usage-value { font-size: 28px; font-weight: 700; color: var(--accent-purple); }
        .usage-label { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
        
        .signals-list { max-height: 400px; overflow-y: auto; }
        .signal-card {
            display: flex; align-items: center; padding: 16px; margin-bottom: 12px;
            background: var(--bg-secondary); border-radius: 12px; border-left: 4px solid;
            transition: transform 0.2s;
        }
        .signal-call { border-left-color: var(--accent-green); }
        .signal-put { border-left-color: var(--accent-red); }
        .signal-icon {
            width: 48px; height: 48px; border-radius: 12px; display: flex;
            align-items: center; justify-content: center; font-size: 24px; margin-right: 16px;
        }
        .signal-call .signal-icon { background: rgba(0, 210, 106, 0.15); }
        .signal-put .signal-icon { background: rgba(255, 71, 87, 0.15); }
        .signal-info { flex: 1; }
        .signal-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
        .signal-confidence { font-size: 24px; font-weight: 700; }
        .signal-call .signal-confidence { color: var(--accent-green); }
        .signal-put .signal-confidence { color: var(--accent-red); }
        
        /* Colors */
        .text-green { color: var(--accent-green); }
        .text-red { color: var(--accent-red); }
        
        /* Timeframe Selector */
        .timeframe-selector {
            display: flex; gap: 4px; margin-left: auto;
        }
        .tf-btn {
            padding: 6px 12px; border-radius: 6px;
            background: var(--bg-secondary); border: 1px solid var(--border-color);
            color: var(--text-secondary); cursor: pointer; font-size: 12px;
            transition: all 0.2s; font-weight: 500;
        }
        .tf-btn:hover { border-color: var(--accent-purple); color: var(--text-primary); }
        .tf-btn.active { background: var(--accent-purple); border-color: var(--accent-purple); color: white; }
        
        /* Live indicator */
        .live-indicator {
            display: flex; align-items: center; gap: 6px;
            font-size: 11px; color: var(--accent-green); margin-left: 12px;
        }
        .live-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--accent-green); animation: pulse-live 1.5s infinite;
        }
        @keyframes pulse-live {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="logo">
                <span style="font-size: 32px;">🤖</span>
                <h1>AI Trading Dashboard</h1>
            </div>
            <div class="header-right">
                <div class="index-toggles" id="index-toggles"></div>
                <div id="status-badge" class="status-badge status-stopped">
                    <span class="pulse pulse-red"></span>
                    <span id="status-text">System Stopped</span>
                </div>
                
                <!-- User Menu -->
                <div class="user-menu">
                    <button class="user-btn" onclick="toggleUserMenu()">
                        <div class="user-avatar" id="user-avatar">?</div>
                        <span id="user-name">User</span>
                        <span class="sub-badge sub-free" id="user-sub">FREE</span>
                    </button>
                    <div class="user-dropdown" id="user-dropdown">
                        <div class="user-info">
                            <div id="user-fullname" style="font-weight: 600;">User</div>
                            <div class="user-email" id="user-email">user@example.com</div>
                            <div style="margin-top: 8px;">
                                <span class="wallet-badge" id="user-wallet">₹0</span>
                            </div>
                        </div>
                        <a href="/wallet" class="user-dropdown-item">💰 My Wallet</a>
                        <a href="/subscribe" class="user-dropdown-item">💎 Subscription</a>
                        <a href="/admin" class="user-dropdown-item" id="admin-link" style="display: none;">🔐 Admin Panel</a>
                        <a href="#" class="user-dropdown-item danger" onclick="logout()">🚪 Logout</a>
                    </div>
                </div>
            </div>
        </header>
        
        <div class="dashboard-grid">
            <!-- Chart Section -->
            <div class="card chart-section">
                <div class="card-header" style="margin-bottom: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                        <span class="card-title">📈 LIVE MARKET CHART</span>
                        <div class="chart-controls" id="chart-tabs">
                            <!-- Tabs generated by JS -->
                        </div>
                        <div class="timeframe-selector" id="timeframe-selector">
                            <button class="tf-btn" data-tf="1" onclick="setTimeframe(1)">1m</button>
                            <button class="tf-btn" data-tf="3" onclick="setTimeframe(3)">3m</button>
                            <button class="tf-btn active" data-tf="5" onclick="setTimeframe(5)">5m</button>
                            <button class="tf-btn" data-tf="15" onclick="setTimeframe(15)">15m</button>
                        </div>
                        <div class="live-indicator">
                            <div class="live-dot"></div>
                            <span id="last-update">Updating...</span>
                        </div>
                    </div>
                </div>
                <div id="chart-container"></div>
            </div>
            
            <!-- Index Cards -->
            <div class="indices-section">
                <div class="indices-grid" id="indices-grid"></div>
            </div>
            
            <!-- Signals Panel -->
            <div class="card signals-panel">
                <div class="card-header">
                    <span class="card-title">🎯 Trading Signals</span>
                    <span id="signals-badge" style="font-size: 12px; color: var(--text-secondary);">0 signals today</span>
                </div>
                <div id="signals-list" class="signals-list">
                    <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                        Waiting for signals...
                    </div>
                </div>
            </div>
            
            <!-- Usage Stats -->
            <div class="card usage-stats">
                <div class="card-header"><span class="card-title">💰 API Usage</span></div>
                <div class="usage-grid">
                    <div class="usage-item">
                        <div id="api-calls" class="usage-value">0</div>
                        <div class="usage-label">API Calls</div>
                    </div>
                    <div class="usage-item">
                        <div id="alerts-sent" class="usage-value">0</div>
                        <div class="usage-label">Alerts</div>
                    </div>
                    <div class="usage-item" style="grid-column: span 2;">
                        <div id="cost" class="usage-value">₹0</div>
                        <div class="usage-label">Estimated Cost</div>
                    </div>
                </div>
            </div>
            
            <!-- Virtual Trading Showcase -->
            <div class="card" style="grid-column: span 12; margin-top: 20px;">
                <div class="card-header">
                    <span class="card-title">💰 Virtual Trading Performance (Paper Trading)</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 20px;">
                    <div class="usage-item">
                        <div id="vt-total-pnl" class="usage-value" style="font-size: 32px;">₹0</div>
                        <div class="usage-label">Total P&L</div>
                    </div>
                    <div class="usage-item">
                        <div id="vt-today-pnl" class="usage-value">₹0</div>
                        <div class="usage-label">Today's P&L</div>
                    </div>
                    <div class="usage-item">
                        <div id="vt-win-rate" class="usage-value">0%</div>
                        <div class="usage-label">Win Rate</div>
                    </div>
                    <div class="usage-item">
                        <div id="vt-total-trades" class="usage-value">0</div>
                        <div class="usage-label">Total Trades</div>
                    </div>
                    <div class="usage-item">
                        <div id="vt-open-trades" class="usage-value">0</div>
                        <div class="usage-label">Open Positions</div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <!-- Recent Trades -->
                    <div>
                        <h4 style="margin-bottom: 12px; color: var(--text-secondary);">📋 Recent Trades</h4>
                        <div id="vt-recent-trades" style="max-height: 200px; overflow-y: auto;">
                            <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                                No trades yet...
                            </div>
                        </div>
                    </div>
                    
                    <!-- Open Positions -->
                    <div>
                        <h4 style="margin-bottom: 12px; color: var(--text-secondary);">📊 Open Positions</h4>
                        <div id="vt-open-positions" style="max-height: 200px; overflow-y: auto;">
                            <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                                No open positions...
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // --- GLOBAL STATE ---
        // Declare all global variables at the top to avoid TDZ issues
        let currentChartIndex = 'NIFTY'; // Default
        let currentTimeframe = 5; // Default 5 minutes
        let chartData = {}; // Cache data
        let allSignals = [];
        let indexConfig = {};
        let chartRefreshInterval = null;
        
        // Price Lines for Indicators
        let supportLine = null;
        let resistanceLine = null;
        let vwapLine = null;

        
        // --- CHART SETUP ---
        let chart = null;
        let candleSeries = null;
        let isChartReady = false;
        
        function initializeChart() {
            const chartContainer = document.getElementById('chart-container');
            chart = LightweightCharts.createChart(chartContainer, {
                layout: { 
                    background: { color: '#16213e' }, 
                    textColor: '#d1d4dc',
                },
                grid: { 
                    vertLines: { color: '#2d2d44' }, 
                    horzLines: { color: '#2d2d44' }, 
                },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: '#2d2d44' },
                timeScale: { borderColor: '#2d2d44', timeVisible: true },
            });
            
            candleSeries = chart.addCandlestickSeries({
                upColor: '#00d26a',
                downColor: '#ff4757',
                borderVisible: false,
                wickUpColor: '#00d26a',
                wickDownColor: '#ff4757',
            });
            
            // Resize chart
            new ResizeObserver(entries => {
                if (entries.length === 0 || entries[0].target !== chartContainer) { return; }
                const newRect = entries[0].contentRect;
                chart.applyOptions({ height: newRect.height, width: newRect.width });
            }).observe(chartContainer);
            
            isChartReady = true;
        }
        
        
        // --- DATA FUNCTIONS ---
        
        function updateIndicators(data) {
            if (!isChartReady || !candleSeries) return;
            
            // Remove old lines
            if (supportLine) candleSeries.removePriceLine(supportLine);
            if (resistanceLine) candleSeries.removePriceLine(resistanceLine);
            if (vwapLine) candleSeries.removePriceLine(vwapLine);
            
            // Add new lines
            if (data.support) {
                supportLine = candleSeries.createPriceLine({
                    price: data.support,
                    color: '#00d26a',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: 'SUPPORT',
                });
            }
            
            if (data.resistance) {
                resistanceLine = candleSeries.createPriceLine({
                    price: data.resistance,
                    color: '#ff4757',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: 'RESISTANCE',
                });
            }
            
            if (data.vwap) {
                vwapLine = candleSeries.createPriceLine({
                    price: data.vwap,
                    color: '#5352ed',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'VWAP',
                });
            }
        }
        
        async function fetchCandles(indexName) {
            if (!isChartReady || !candleSeries) return;
            
            try {
                const response = await fetch(`/api/candles/${indexName}?interval=${currentTimeframe}`);
                const data = await response.json();
                if (data.candles && data.candles.length > 0) {
                    // Format for Lightweight Charts
                    // Converting strings timestamps to UNIX timestamps (seconds)
                    const formatted = data.candles.map(c => ({
                        time: new Date(c.timestamp).getTime() / 1000 + 19800,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close
                    })).sort((a, b) => a.time - b.time);
                    
                    // Deduplicate times
                    const uniqueData = [];
                    const timeMap = new Map();
                    for (const item of formatted) {
                        if (!timeMap.has(item.time)) {
                            timeMap.set(item.time, true);
                            uniqueData.push(item);
                        }
                    }
                    
                    if (currentChartIndex === indexName) {
                        // Check if we need to update the last candle or add a new one
                        const existingData = chartData[indexName] || [];
                        const lastExisting = existingData[existingData.length - 1];
                        const lastNew = uniqueData[uniqueData.length - 1];
                        
                        if (lastExisting && lastNew && lastExisting.time === lastNew.time) {
                            // Same candle - update it (price movement within same candle)
                            candleSeries.update(lastNew);
                        } else {
                            // New candle or initial load - set all data
                            candleSeries.setData(uniqueData);
                        }
                        
                        updateMarkers(indexName);
                        
                        // Update indicators from response
                        if (data.support || data.resistance || data.vwap) {
                            updateIndicators({
                                support: data.support,
                                resistance: data.resistance,
                                vwap: data.vwap
                            });
                        }
                        
                        // Update last update time with LIVE indicator
                        const now = new Date();
                        const liveText = data.live ? '🟢 LIVE' : '⚪ Cached';
                        document.getElementById('last-update').textContent = 
                            `${liveText} ${now.toLocaleTimeString('en-IN', {hour: '2-digit', minute: '2-digit', second: '2-digit'})}`;
                    }
                    
                    chartData[indexName] = uniqueData;
                }
            } catch (e) { console.error("Error fetching candles:", e); }
        }
        
        // Timeframe selector function
        function setTimeframe(tf) {
            currentTimeframe = tf;
            
            // Update button states
            document.querySelectorAll('.tf-btn').forEach(btn => {
                btn.classList.toggle('active', parseInt(btn.dataset.tf) === tf);
            });
            
            // Show loading state
            document.getElementById('last-update').textContent = 'Loading...';
            
            // Clear cache and chart data
            chartData = {};
            
            // Clear current chart and refetch
            if (candleSeries) {
                candleSeries.setData([]);
            }
            
            // Fetch new data with the new timeframe
            fetchCandles(currentChartIndex);
        }
        
        // Start chart auto-refresh (every 5 seconds for live updates)
        function startChartRefresh() {
            if (chartRefreshInterval) clearInterval(chartRefreshInterval);
            chartRefreshInterval = setInterval(() => {
                fetchCandles(currentChartIndex);
            }, 5000); // Refresh every 5 seconds for real-time feel
        }
        
        function updateMarkers(indexName) {
            if (!isChartReady || !candleSeries) return;
            
            // Filter signals for this index (only recent ones)
            const indexSignals = allSignals.filter(s => 
                (s.index === indexName || (indexName === 'NIFTY' && !s.index))
            ).slice(0, 10); // Only show last 10 signals
            
            const candles = chartData[indexName] || [];
            if (candles.length === 0) return;
            
            const markers = [];
            
            indexSignals.forEach((s, idx) => {
                // Calculate signal time - spread markers across recent candles
                // Use chart_time if available, otherwise distribute across last candles
                let markerTime;
                
                if (s.chart_time) {
                    // Use actual signal time
                    markerTime = s.chart_time + 19800; // Add IST offset
                } else {
                    // Distribute markers across recent candles so they don't overlap
                    const candleIndex = Math.max(0, candles.length - 1 - idx * 2);
                    markerTime = candles[candleIndex].time;
                }
                
                markers.push({
                    time: markerTime,
                    position: s.signal === 'CALL' ? 'belowBar' : 'aboveBar',
                    color: s.signal === 'CALL' ? '#00d26a' : '#ff4757',
                    shape: s.signal === 'CALL' ? 'arrowUp' : 'arrowDown',
                    text: `${s.signal} @ ${s.strike}`,
                    size: 2,
                });
            });
            
            // Sort markers by time to avoid library errors
            markers.sort((a, b) => a.time - b.time);
            
            candleSeries.setMarkers(markers);
        }
        
        // Render Index Toggles & Cards 
        function renderUI(data) {
            // Update Toggles - always rebuild to reflect current state
            const toggleContainer = document.getElementById('index-toggles');
            let togglesHtml = '';
            for (const [name, config] of Object.entries(data.indices)) {
                const active = config.enabled ? 'active' : '';
                togglesHtml += `
                    <div class="index-toggle ${active}" data-index="${name}" onclick="toggleIndex('${name}')">
                        <span>${config.display_name}</span>
                        <div class="toggle-switch"></div>
                    </div>`;
            }
            toggleContainer.innerHTML = togglesHtml;
            
            // Update Chart Tabs
            const tabContainer = document.getElementById('chart-tabs');
            let tabsHtml = '';
            for (const [name, config] of Object.entries(data.indices)) {
                if (!config.enabled) continue;
                const active = name === currentChartIndex ? 'active' : '';
                tabsHtml += `<div class="chart-tab ${active}" onclick="switchChart('${name}')">${config.display_name}</div>`;
            }
            tabContainer.innerHTML = tabsHtml;
            
            // Update Index Cards
            const cardContainer = document.getElementById('indices-grid');
            cardContainer.innerHTML = ''; 
            for (const [name, config] of Object.entries(data.indices)) {
                if (!config.enabled) continue;
                const m = data.market_data[name] || {};
                cardContainer.innerHTML += `
                    <div class="index-card">
                        <div class="index-card-header">
                            <span class="index-name">${config.display_name}</span>
                            <span class="index-price">${m.spot_price ? m.spot_price.toLocaleString() : '--'}</span>
                        </div>
                        <div class="index-stats">
                            <div class="mini-stat"><div class="mini-stat-label">PCR</div><div class="mini-stat-value ${m.pcr<1?'green':'red'}">${m.pcr?.toFixed(2)||'--'}</div></div>
                            <div class="mini-stat"><div class="mini-stat-label">VWAP</div><div class="mini-stat-value">${m.vwap?.toLocaleString()||'--'}</div></div>
                            <div class="mini-stat"><div class="mini-stat-label">SUP</div><div class="mini-stat-value green">${m.support||'--'}</div></div>
                            <div class="mini-stat"><div class="mini-stat-label">RES</div><div class="mini-stat-value red">${m.resistance||'--'}</div></div>
                        </div>
                    </div>`;
            }
            
            // Update Stats
            document.getElementById('api-calls').textContent = data.usage.api_calls;
            document.getElementById('alerts-sent').textContent = data.usage.alerts_sent;
            document.getElementById('cost').textContent = '₹' + data.usage.estimated_cost_inr.toFixed(2);
            updateStatus(data.system_status);
            
            // Update Signals
            allSignals = data.signals;
            const signalList = document.getElementById('signals-list');
            if (data.signals.length > 0) {
                signalList.innerHTML = data.signals.map(s => `
                    <div class="signal-card signal-${s.signal.toLowerCase()}">
                        <div class="signal-icon">${s.signal==='CALL'?'📈':'📉'}</div>
                        <div class="signal-info">
                            <div class="signal-title">${s.index||''} ${s.signal} ${s.strike}</div>
                            <div style="font-size:12px; opacity:0.7">${s.reasoning.substring(0,60)}...</div>
                        </div>
                        <div class="signal-confidence">${s.confidence}%</div>
                    </div>
                `).join('');
                document.getElementById('signals-badge').textContent = data.signals.length + ' signals today';
                
                // Update markers on chart
                updateMarkers(currentChartIndex);
            }
            
            // Update Indicators (Lines)
            const currentData = data.market_data[currentChartIndex] || {};
            updateIndicators(currentData);
        }

        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                renderUI(data);
                
                // Fetch candle updates for current chart
                fetchCandles(currentChartIndex);
                
                // Fetch virtual trading data
                fetchVirtualTrades();
                
            } catch (e) { console.error(e); }
        }
        
        async function fetchVirtualTrades() {
            try {
                const res = await fetch('/api/virtual_trades');
                const data = await res.json();
                
                if (data.error) return;
                
                const stats = data.stats || {};
                
                // Update stats display
                const totalPnl = stats.total_pnl || 0;
                const todayPnl = stats.todays_pnl || 0;
                
                document.getElementById('vt-total-pnl').textContent = `₹${totalPnl >= 0 ? '+' : ''}${totalPnl.toLocaleString()}`;
                document.getElementById('vt-total-pnl').style.color = totalPnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                
                document.getElementById('vt-today-pnl').textContent = `₹${todayPnl >= 0 ? '+' : ''}${todayPnl.toLocaleString()}`;
                document.getElementById('vt-today-pnl').style.color = todayPnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                
                document.getElementById('vt-win-rate').textContent = `${stats.win_rate || 0}%`;
                document.getElementById('vt-total-trades').textContent = stats.total_trades || 0;
                document.getElementById('vt-open-trades').textContent = stats.open_trades || 0;
                
                // Render recent trades
                const recentTradesDiv = document.getElementById('vt-recent-trades');
                if (data.recent_trades && data.recent_trades.length > 0) {
                    recentTradesDiv.innerHTML = data.recent_trades.map(t => {
                        const emoji = t.pnl > 0 ? '✅' : (t.pnl < 0 ? '❌' : '⏳');
                        const pnlColor = t.pnl > 0 ? 'var(--accent-green)' : (t.pnl < 0 ? 'var(--accent-red)' : 'var(--text-secondary)');
                        const statusText = t.status === 'TARGET_HIT' ? 'Target' : (t.status === 'SL_HIT' ? 'SL' : 'Closed');
                        return `
                            <div style="display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; background: var(--bg-secondary); border-radius: 8px; margin-bottom: 8px; border-righ: 3px solid ${pnlColor};">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 600;">${emoji} ${t.signal_type} ${t.index} ${t.strike}</span>
                                    <span style="color: ${pnlColor}; font-weight: 600;">₹${t.pnl >= 0 ? '+' : ''}${(t.pnl || 0).toLocaleString()}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 11px; opacity: 0.7;">
                                    <span>In: ₹${t.entry_premium} | Out: ₹${t.exit_premium}</span>
                                    <span>${statusText} | Lot: ${t.lot_size}</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                } else {
                    recentTradesDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary);">No trades yet...</div>';
                }
                
                // Render open positions
                const openPosDiv = document.getElementById('vt-open-positions');
                if (data.open_trades && data.open_trades.length > 0) {
                    openPosDiv.innerHTML = data.open_trades.map(t => {
                        const pnlColor = t.current_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                        return `
                            <div style="display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; background: var(--bg-secondary); border-radius: 8px; margin-bottom: 8px; border-left: 3px solid ${t.signal_type === 'CALL' ? 'var(--accent-green)' : 'var(--accent-red)'};">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 600;">🔄 ${t.signal_type} ${t.index} ${t.strike}</span>
                                    <span style="color: ${pnlColor}; font-weight: 600;">₹${t.current_pnl >= 0 ? '+' : ''}${(t.current_pnl || 0).toLocaleString()}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 11px; opacity: 0.7;">
                                    <span>Entry: ₹${t.entry_premium} | LTP: ₹${t.current_premium?.toFixed(1)}</span>
                                    <span>Lot: ${t.lot_size} | T: +${t.target_points} | SL: -${t.stop_loss_points}</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                } else {
                    openPosDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary);">No open positions...</div>';
                }
                
            } catch (e) { console.error('Error fetching virtual trades:', e); }
        }
        
        function switchChart(indexName) {
            currentChartIndex = indexName;
            fetchCandles(indexName);
            fetchState(); 
        }
        
        function toggleIndex(name) {
            fetch(`/api/toggle_index/${name}`, {method: 'POST'}).then(() => fetchState());
        }
        
        function updateStatus(status) {
            const badge = document.getElementById('status-badge');
            const text = document.getElementById('status-text');
            const pulse = badge.querySelector('.pulse');
            if (status === 'Running') {
                badge.className = 'status-badge status-running';
                pulse.className = 'pulse pulse-green';
                text.textContent = 'System Running';
            } else {
                badge.className = 'status-badge status-stopped';
                pulse.className = 'pulse pulse-red';
                text.textContent = 'System Stopped';
            }
        }
        
        // User Menu Functions
        function toggleUserMenu() {
            document.getElementById('user-dropdown').classList.toggle('active');
        }
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.user-menu')) {
                document.getElementById('user-dropdown').classList.remove('active');
            }
        });
        
        async function loadUserData() {
            try {
                const res = await fetch('/api/auth/me');
                if (!res.ok) {
                    window.location.href = '/login';
                    return;
                }
                const user = await res.json();
                
                // Update UI
                const initials = (user.name || 'U').split(' ').map(n => n[0]).join('').toUpperCase();
                document.getElementById('user-avatar').textContent = initials;
                document.getElementById('user-name').textContent = user.name || 'User';
                document.getElementById('user-fullname').textContent = user.name || 'User';
                document.getElementById('user-email').textContent = user.email || '';
                document.getElementById('user-wallet').textContent = '₹' + (user.wallet_balance || 0).toLocaleString();
                
                // Subscription badge
                const sub = user.subscription || 'free';
                const subEl = document.getElementById('user-sub');
                subEl.textContent = sub.toUpperCase();
                subEl.className = 'sub-badge sub-' + sub;
                
                // Show admin link if admin
                if (user.is_admin) {
                    document.getElementById('admin-link').style.display = 'flex';
                }
            } catch (e) {
                console.error('Error loading user:', e);
            }
        }
        
        async function logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/login';
        }
        
        // Initialize and start - wait for everything to be ready
        function startApp() {
            // Check if library is loaded
            if (typeof LightweightCharts === 'undefined') {
                console.log('Waiting for LightweightCharts library...');
                setTimeout(startApp, 100);
                return;
            }
            
            try {
                loadUserData(); // Load user data
                initializeChart();
                fetchState();
                setInterval(fetchState, 2000);
                startChartRefresh(); // Start live chart updates
                console.log('Dashboard initialized successfully');
            } catch (e) {
                console.error('Init error:', e);
                setTimeout(startApp, 500);
            }
        }
        
        // Start when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', startApp);
        } else {
            startApp();
        }
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    """Render the dashboard."""
    # Check if user is logged in
    if AUTH_ENABLED:
        user = get_current_user()
        if not user:
            from flask import redirect
            return redirect('/login')
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/state')
def get_state():
    """Get current dashboard state."""
    usage = get_usage_monitor().get_current_stats()
    index_mgr = get_index_manager()
    
    indices = {}
    for name, config in index_mgr.indices.items():
        indices[name] = {
            "name": config.name,
            "display_name": config.display_name,
            "enabled": config.enabled,
        }
    
    return jsonify({
        "signals": dashboard_state["signals"],
        "market_data": dashboard_state["market_data"],
        "system_status": dashboard_state["system_status"],
        "usage": usage,
        "indices": indices,
    })


@app.route('/api/candles/<index_name>')
def get_candles(index_name):
    """Get LIVE candle data for a specific index. Supports ?interval=1,3,5,15 (minutes)."""
    interval = request.args.get('interval', '5')  # Default 5 min
    
    # Get cached data for support/resistance
    cached_data = dashboard_state["market_data"].get(index_name, {})
    
    # Try to fetch live candles from Upstox
    try:
        from data_fetcher import fetch_candles_sync
        from index_config import AVAILABLE_INDICES
        
        index_config = AVAILABLE_INDICES.get(index_name)
        if not index_config:
            # Fallback to cached
            return jsonify({
                "candles": cached_data.get("candles", []), 
                "interval": interval, 
                "live": False,
                "support": cached_data.get("support", 0),
                "resistance": cached_data.get("resistance", 0),
                "vwap": cached_data.get("vwap", 0)
            })
        
        # Fetch live candles using the sync helper
        candles = fetch_candles_sync(
            instrument_key=index_config.symbol,
            interval=str(interval),
            unit="minutes"
        )
        
        if candles:
            # Format candles for frontend
            formatted = [
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume
                }
                for c in candles
            ]
            
            # Update cache
            if index_name in dashboard_state["market_data"]:
                dashboard_state["market_data"][index_name]["candles"] = formatted
            
            return jsonify({
                "candles": formatted, 
                "interval": interval, 
                "live": True,
                "support": cached_data.get("support", 0),
                "resistance": cached_data.get("resistance", 0),
                "vwap": cached_data.get("vwap", 0)
            })
        else:
            # Fallback to cached
            return jsonify({
                "candles": cached_data.get("candles", []), 
                "interval": interval, 
                "live": False,
                "support": cached_data.get("support", 0),
                "resistance": cached_data.get("resistance", 0),
                "vwap": cached_data.get("vwap", 0)
            })
            
    except Exception as e:
        # Fallback to cached data on any error
        return jsonify({
            "candles": cached_data.get("candles", []), 
            "interval": interval, 
            "live": False, 
            "error": str(e),
            "support": cached_data.get("support", 0),
            "resistance": cached_data.get("resistance", 0),
            "vwap": cached_data.get("vwap", 0)
        })


@app.route('/api/toggle_index/<index_name>', methods=['POST'])
def toggle_index(index_name):
    """Toggle an index on/off."""
    index_mgr = get_index_manager()
    new_state = index_mgr.toggle_index(index_name)
    return jsonify({"status": "ok", "enabled": new_state})


@app.route('/api/add_signal', methods=['POST'])
def api_add_signal():
    """Add a signal via API."""
    data = request.json
    add_signal(data)
    return jsonify({"status": "ok"})


@app.route('/api/performance')
def api_performance():
    """Get signal performance statistics."""
    try:
        from signal_tracker import get_signal_tracker
        tracker = get_signal_tracker()
        index_name = request.args.get('index', None)
        stats = tracker.get_stats(index_name)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/signals_history')
def api_signals_history():
    """Get signal history."""
    try:
        from signal_tracker import get_signal_tracker
        tracker = get_signal_tracker()
        limit = int(request.args.get('limit', 20))
        signals = tracker.signals[-limit:][::-1]  # Most recent first
        return jsonify(signals)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/virtual_trades')
def api_virtual_trades():
    """Get virtual trading statistics and showcase."""
    try:
        from virtual_trader import get_virtual_trader
        trader = get_virtual_trader()
        stats = trader.get_stats()
        
        # Add recent trades
        recent = [t.to_dict() for t in trader.trades[-10:][::-1]]
        
        return jsonify({
            "stats": stats,
            "recent_trades": recent,
            "open_trades": [t.to_dict() for t in trader.get_open_trades()],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/virtual_showcase')
def api_virtual_showcase():
    """Get virtual trading showcase message."""
    try:
        from virtual_trader import get_virtual_trader
        trader = get_virtual_trader()
        return jsonify({
            "message": trader.get_showcase_message(),
            "stats": trader.get_stats(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_dashboard(host='0.0.0.0', port=None):
    """Run the dashboard server."""
    import os
    # Use PORT from environment (Railway sets this) or default to 8080
    port = port or int(os.environ.get('PORT', 8080))
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    run_dashboard()
