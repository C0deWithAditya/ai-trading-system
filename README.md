# 🤖 AI Trading Dashboard

A real-time F&O trading system with AI-powered signals, live charts, and Telegram alerts.

---

## 🚀 Quick Start

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure `.env` File
Copy the example and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env` with your API keys:
```env
# Upstox API (Required)
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=  # Generated in Step 3

# Gemini AI (Required for AI signals)
GEMINI_API_KEY=your_gemini_key

# Telegram (Optional but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_ENABLED=true
```

### Step 3: Generate Upstox Access Token
```bash
python3 auth_helper.py
```
- Enter your API Key and Secret
- Login to Upstox in the browser
- Token will be displayed - copy it to `.env`

### Step 4: Run the System
```bash
python3 main.py
```

Dashboard will open at: **http://127.0.0.1:8080**

---

## 📋 Daily Usage

**Every day before market opens (token expires daily):**
```bash
# 1. Generate new token
python3 auth_helper.py

# 2. Start the system
python3 main.py
```

---

## 🔑 Getting API Keys

### Upstox API
1. Go to https://api.upstox.com
2. Create an app to get API Key & Secret
3. **Important**: Enable F&O segment in your Upstox account

### Gemini API (Free)
1. Go to https://aistudio.google.com/app/apikey
2. Create API key

### Telegram Bot
1. Open Telegram, search **@BotFather**
2. Send `/newbot` and follow instructions
3. Copy the bot token
4. Send any message to your bot
5. Get chat ID:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```

---

## 📊 Features

- ✅ Live candlestick charts
- ✅ AI-powered trading signals (Gemini)
- ✅ Multi-index support (NIFTY, Bank NIFTY, Fin NIFTY, etc.)
- ✅ Real-time Telegram alerts
- ✅ Technical indicators (Support, Resistance, VWAP, PCR)
- ✅ API usage tracking

---

## ⏰ Market Hours

System actively monitors: **9:15 AM - 3:30 PM IST** (Mon-Fri)

Outside market hours, system waits automatically.

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Token expired | Run `python3 auth_helper.py` again |
| F&O data error | Enable F&O segment in Upstox app |
| No AI signals | Check GEMINI_API_KEY in .env |
| No Telegram alerts | Verify bot token and chat ID |

---

## 📁 Project Structure

```
trading_app/
├── main.py           # Main entry point
├── dashboard.py      # Web dashboard
├── auth_helper.py    # Token generator
├── data_fetcher.py   # Upstox API client
├── ai_analyzer.py    # Gemini AI integration
├── notifier.py       # Telegram alerts
├── strategy.py       # Signal generation
├── indicators.py     # Technical analysis
└── .env              # Your configuration
```

---

**Made with ❤️ for Indian F&O Traders**
