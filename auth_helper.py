"""
Upstox OAuth Authentication Helper.
Helps generate access tokens for the Upstox API.

Usage:
    python auth_helper.py

This script helps you:
1. Generate the authorization URL
2. Start a local server to receive the auth code
3. Exchange the auth code for an access token
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode, quote
import requests
import json


class AuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""
    
    auth_code = None
    
    def do_GET(self):
        """Handle GET request with auth code."""
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if "code" in params:
            AuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            response = """
            <html>
            <head><title>Authorization Successful</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">✓ Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <p>Auth code received: <code>{}</code></p>
            </body>
            </html>
            """.format(self.auth_code[:20] + "...")
            self.wfile.write(response.encode())
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error: No authorization code received</h1>")
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def get_authorization_url(api_key: str, redirect_uri: str) -> str:
    """Generate the authorization URL."""
    base_url = "https://api.upstox.com/v2/login/authorization/dialog"
    params = {
        "response_type": "code",
        "client_id": api_key,
        "redirect_uri": redirect_uri,
    }
    return f"{base_url}?{urlencode(params)}"


def exchange_code_for_token(
    auth_code: str, 
    api_key: str, 
    api_secret: str, 
    redirect_uri: str
) -> dict:
    """Exchange authorization code for access token."""
    url = "https://api.upstox.com/v2/login/authorization/token"
    
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    data = {
        "code": auth_code,
        "client_id": api_key,
        "client_secret": api_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()


def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         UPSTOX OAUTH AUTHENTICATION HELPER               ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Get API credentials
    api_key = os.getenv("UPSTOX_API_KEY") or input("Enter your Upstox API Key: ").strip()
    api_secret = os.getenv("UPSTOX_API_SECRET") or input("Enter your Upstox API Secret: ").strip()
    
    if not api_key or not api_secret:
        print("Error: API Key and Secret are required!")
        sys.exit(1)
    
    # Set redirect URI (local server)
    redirect_uri = "http://127.0.0.1:5000/callback"
    
    print(f"\n📌 Redirect URI: {redirect_uri}")
    print("   Make sure this matches your app's redirect URI in Upstox Developer Portal!\n")
    
    # Generate authorization URL
    auth_url = get_authorization_url(api_key, redirect_uri)
    
    print("=" * 60)
    print("STEP 1: Authorization")
    print("=" * 60)
    print(f"\nOpening browser to authorize...")
    print(f"\nIf browser doesn't open, visit this URL manually:\n{auth_url}\n")
    
    # Start local server to receive callback
    server_address = ("127.0.0.1", 5000)
    httpd = HTTPServer(server_address, AuthCallbackHandler)
    
    # Open browser
    webbrowser.open(auth_url)
    
    print("Waiting for authorization callback...")
    print("(Complete the login in your browser)\n")
    
    # Wait for callback
    while AuthCallbackHandler.auth_code is None:
        httpd.handle_request()
    
    auth_code = AuthCallbackHandler.auth_code
    print(f"✓ Auth code received: {auth_code[:20]}...\n")
    
    print("=" * 60)
    print("STEP 2: Token Exchange")
    print("=" * 60)
    
    # Exchange for access token
    print("\nExchanging auth code for access token...")
    
    token_response = exchange_code_for_token(
        auth_code=auth_code,
        api_key=api_key,
        api_secret=api_secret,
        redirect_uri=redirect_uri,
    )
    
    if "access_token" in token_response:
        access_token = token_response["access_token"]
        print("\n✓ Access token generated successfully!\n")
        print("=" * 60)
        print("ACCESS TOKEN:")
        print("=" * 60)
        print(f"\n{access_token}\n")
        print("=" * 60)
        
        # Save to .env file
        save = input("\nSave to .env file? (y/n): ").strip().lower()
        if save == "y":
            env_content = f"""# Upstox API Configuration
UPSTOX_API_KEY={api_key}
UPSTOX_API_SECRET={api_secret}
UPSTOX_ACCESS_TOKEN={access_token}

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ENABLED=true
"""
            with open(".env", "w") as f:
                f.write(env_content)
            print("✓ Saved to .env file")
        
        print("\n⚠️  IMPORTANT:")
        print("   - Access token is valid for one trading day")
        print("   - You need to regenerate it daily before market opens")
        print("   - Store it securely and never share it")
        
    else:
        print("\n❌ Error getting access token:")
        print(json.dumps(token_response, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
