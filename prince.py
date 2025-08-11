#!/usr/bin/env python3
"""Facebook Auto Commenter - Complete application in one file"""

from flask import Flask, request, jsonify, render_template_string
import requests
import os
import re
import time
import threading
import uuid
import traceback
from requests.exceptions import RequestException

# Try to import Selenium - it's optional
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    print("Warning: Selenium not available - cookie extraction will be disabled")
    SELENIUM_AVAILABLE = False

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Global variables
running_tasks = {}
task_outputs = {}
GRAPH_API_URL = "https://graph.facebook.com/v18.0"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# HTML Templates
PAGES_HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>FB Pages — Tokens & Cookies</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background-image:url('https://i.postimg.cc/L51fQrQH/681be2a77443fb2f2f74fd42da1bc40f.jpg');background-size:cover;background-position:center;background-repeat:no-repeat;background-attachment:fixed;color:white;min-height:100vh}
.container{max-width:900px;margin:0 auto;background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border-radius:20px;padding:30px;box-shadow:0 8px 32px 0 rgba(31,38,135,0.37);border:1px solid rgba(255,255,255,0.18);margin-top:50px}
.card{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.2);padding:20px;margin:20px 0;border-radius:10px}
.row-flex{display:flex;align-items:center;gap:15px}
img.dp{width:64px;height:64px;border-radius:50%;border:2px solid #4ecdc4}
.token,.cookies{background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);word-break:break-all;color:#00ff00;font-family:'Courier New',monospace;font-size:12px;margin:8px 0}
.copy{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);color:#fff;border:none;padding:8px 15px;border-radius:6px;cursor:pointer;margin-left:8px;font-weight:bold}
.copy:hover{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,0.3)}
h1{text-align:center;background:linear-gradient(45deg,#ff6b6b,#4ecdc4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-weight:bold}
.form-control{background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.3);border-radius:10px;color:white;padding:12px}
.form-control:focus{background:rgba(255,255,255,0.3);border-color:#4ecdc4;box-shadow:0 0 0 0.2rem rgba(78,205,196,0.25);color:white}
.form-control::placeholder{color:rgba(255,255,255,0.7)}
.form-label{color:white;font-weight:500;margin-bottom:8px}
.btn-primary{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);border:none;border-radius:10px;padding:12px 30px;font-weight:bold}
.btn-secondary{background:linear-gradient(45deg,#3742fa,#2f3542);border:none;border-radius:10px;padding:8px 20px;color:white}
small{color:rgba(255,255,255,0.7)}
.alert{border-radius:10px;margin-bottom:20px}
</style>
<script>
function copyText(text){navigator.clipboard.writeText(text).then(()=>alert("Copied to clipboard!")).catch(()=>alert("Failed to copy"))}
</script>
</head>
<body>
<div class="container">
  <h1>Facebook Pages — Tokens & Cookies</h1>
  <div class="text-center mb-4">
    <a href="/" class="btn btn-secondary">← Back to Auto Commenter</a>
  </div>
  <div class="card">
    <form method="POST">
      <div class="mb-3">
        <label class="form-label">Access token (optional)</label>
        <input type="text" class="form-control" name="token" placeholder="Enter Facebook access token (starts with EAA... )" value="{{ request.form.get('token', '') }}">
      </div>
      <div class="mb-3">
        <label class="form-label">Valid Facebook cookies (optional)</label>
        <textarea class="form-control" name="cookies" rows="4" placeholder="Paste cookies string (e.g. c_user=...; xs=...; datr=... )">{{ request.form.get('cookies', '') }}</textarea>
      </div>
      <div class="mb-3">
        <button class="btn btn-primary" type="submit">Extract Pages Info</button>
      </div>
      <small>Provide token OR cookies or both. Cookies must be from the account that manages the pages.</small>
      {% if not selenium_available %}
        <div class="alert alert-warning mt-3">
          <strong>Note:</strong> Cookie extraction is disabled (Selenium not available). Only token-based extraction will work.
        </div>
      {% endif %}
    </form>
  </div>
  {% if error %}
    <div class="alert alert-danger"><strong>Error:</strong> {{ error }}</div>
  {% endif %}
  {% for item in results %}
    <div class="card">
      <div class="row-flex">
        <img class="dp" src="{{ item.picture or 'https://via.placeholder.com/64' }}" alt="Profile Picture">
        <div style="flex:1">
          <strong style="color: #4ecdc4;">{{ item.name }}</strong><br>
          {% if item.token %}
            <div class="token"><b>Token:</b> {{ item.token }}</div>
            <button class="copy" onclick="copyText('{{ item.token }}')">Copy Token</button>
          {% endif %}
          {% if item.cookies %}
            <div class="cookies"><b>Cookies:</b> {{ item.cookies }}</div>
            <button class="copy" onclick="copyText('{{ item.cookies }}')">Copy Cookies</button>
          {% endif %}
        </div>
      </div>
    </div>
  {% endfor %}
</div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>𝙋𝙍𝙄𝙉𝘾𝙀 𝙃𝙀𝙍𝙀🥤</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    <style>
        body{{background-image:url('https://i.postimg.cc/L51fQrQH/681be2a77443fb2f2f74fd42da1bc40f.jpg');background-size:cover;background-position:center;background-repeat:no-repeat;background-attachment:fixed;color:white;min-height:100vh}}
        .container{{max-width:900px;background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border-radius:20px;padding:30px;box-shadow:0 8px 32px 0 rgba(31,38,135,0.37);border:1px solid rgba(255,255,255,0.18);margin-top:50px}}
        .header{{text-align:center;padding-bottom:30px}}
        .header h1{{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-weight:bold;margin-bottom:10px}}
        .form-control{{background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.3);border-radius:10px;color:white;padding:12px;margin-bottom:15px}}
        .form-control:focus{{background:rgba(255,255,255,0.3);border-color:#4ecdc4;box-shadow:0 0 0 0.2rem rgba(78,205,196,0.25);color:white}}
        .form-control::placeholder{{color:rgba(255,255,255,0.7)}}
        .form-label{{color:white;font-weight:500;margin-bottom:8px}}
        .btn-primary{{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);border:none;border-radius:10px;padding:12px 30px;font-weight:bold;transition:transform 0.3s ease}}
        .btn-primary:hover{{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,0.3)}}
        .btn-danger{{background:linear-gradient(45deg,#ff4757,#ff3838);border:none;border-radius:10px;padding:12px 30px;font-weight:bold;transition:transform 0.3s ease}}
        .btn-danger:hover{{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,0.3)}}
        .btn-info{{background:linear-gradient(45deg,#3742fa,#2f3542);border:none;border-radius:10px;padding:8px 20px;font-weight:bold;transition:transform 0.3s ease}}
        .footer{{text-align:center;margin-top:30px;color:rgba(255,255,255,0.8)}}
        .prince-logo{{width:80px;height:80px;border-radius:50%;margin-bottom:20px;border:3px solid #4ecdc4}}
        .stop-section{{margin-top:40px;padding-top:30px;border-top:1px solid rgba(255,255,255,0.2)}}
        .console-section{{margin-top:30px;padding:20px;background:rgba(0,0,0,0.3);border-radius:10px;border:1px solid rgba(255,255,255,0.2)}}
        .console-output{{background:#000;color:#00ff00;padding:15px;border-radius:5px;font-family:'Courier New',monospace;font-size:12px;height:300px;overflow-y:auto;border:1px solid #333}}
        .alert{{border-radius:10px;margin-bottom:20px}}
        .row{{margin:0}}
        .col-md-6{{padding:10px}}
        .auth-section{{border:1px solid rgba(255,255,255,0.2);border-radius:10px;padding:20px;margin-bottom:20px;background:rgba(255,255,255,0.05)}}
        .endless-badge{{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);color:white;padding:5px 15px;border-radius:20px;font-size:12px;font-weight:bold;display:inline-block;margin-left:10px}}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.postimg.cc/VvB52mwW/In-Shot-20250608-213052061.jpg" alt="𝘗𝘙𝘐𝘕𝘊𝘞" class="prince-logo">
            <h1>Facebook Auto Commenter <span class="endless-badge">ENDLESS MODE</span></h1>
            <p>𝙎𝘽𝙍 𝙒𝘼𝙇𝙊 𝙆𝙄 𝙈𝘼 𝙆𝙄 𝘾𝙃𝙊𝙊𝙏 𝙆𝙊 𝙇𝘼𝙉𝘿 𝙎𝙀 𝘾𝙃𝙀𝙀𝙍𝙉𝙀𝙔 𝙒𝘼𝙇𝘼 𝘿𝘼𝙉𝘼𝙑 𝙆𝙄𝙉𝙂 𝙋𝙍𝙄𝙉𝘾𝙀</p>
        </div>

        {error_message}
        {success_message}

        <div class="row">
            <div class="col-md-6">
                <form method="post" action="/start_commenting" enctype="multipart/form-data">
                    <div class="auth-section">
                        <h5>Step 1: Authentication Data</h5>
                        <div class="mb-3">
                            <label for="cookiesInput" class="form-label">Facebook Cookies (one per line)</label>
                            <textarea class="form-control" id="cookiesInput" name="cookiesInput" rows="5" placeholder="Enter your Facebook cookies here (one cookie per line)...&#10;Example:&#10;c_user=123456; xs=abcdef; datr=xyz123&#10;c_user=789012; xs=ghijkl; datr=mno456" required></textarea>
                            <small class="text-muted">Each line should contain one complete cookie string</small>
                        </div>

                        <div class="mb-3">
                            <label for="tokensInput" class="form-label">Facebook Tokens (one per line) - Optional</label>
                            <textarea class="form-control" id="tokensInput" name="tokensInput" rows="3" placeholder="Enter your Facebook access tokens here (one token per line)...&#10;Example:&#10;EAAGxxxxxxxxxxxxxxxx&#10;EAAGyyyyyyyyyyyyyyyy"></textarea>
                            <small class="text-muted">Optional: Leave empty if you only want to use cookies</small>
                        </div>
                    </div>

                    <div class="auth-section">
                        <h5>Step 2: Target Post & Settings</h5>
                        <div class="mb-3">
                            <label for="postId" class="form-label">Facebook Post ID</label>
                            <input type="text" class="form-control" id="postId" name="postId" placeholder="Enter Facebook post ID" required>
                        </div>

                        <div class="mb-3">
                            <label for="commenterName" class="form-label">Commenter Name</label>
                            <input type="text" class="form-control" id="commenterName" name="commenterName" placeholder="Enter name to display with comments" required>
                        </div>

                        <div class="mb-3">
                            <label for="mentionName" class="form-label">Mention Someone (Optional)</label>
                            <input type="text" class="form-control" id="mentionName" name="mentionName" placeholder="Enter Facebook User ID or Profile URL" oninput="formatMention(this)">
                            <small class="text-muted">
                                <strong>How to mention properly (clickable):</strong><br>
                                • <strong>Best:</strong> Facebook User ID: <code>100012345678901</code><br>
                                • Profile URL: <code>https://facebook.com/john.doe</code><br>
                                • Username only: <code>john.doe</code> (may not be clickable)<br>
                                • Leave empty if you don't want to mention anyone<br>
                                <strong>Note:</strong> User ID creates clickable mentions that open their profile!
                            </small>
                        </div>

                        <div class="mb-3">
                            <label for="delay" class="form-label">Delay Between Comments (seconds)</label>
                            <input type="number" class="form-control" id="delay" name="delay" min="1" placeholder="Enter delay in seconds" required>
                        </div>
                    </div>

                    <div class="auth-section">
                        <h5>Step 3: Comments</h5>
                        <div class="mb-3">
                            <label for="commentsInput" class="form-label">Comments (one per line)</label>
                            <textarea class="form-control" id="commentsInput" name="commentsInput" rows="8" placeholder="Enter your comments here (one comment per line)...&#10;Example:&#10;Great post!&#10;Love this!&#10;Amazing content&#10;Keep it up!" required></textarea>
                            <small class="text-muted">Each line will be used as a separate comment</small>
                        </div>
                    </div>

                    <div class="text-center">
                        <button type="submit" class="btn btn-primary" style="padding: 15px 40px; font-size: 16px;">
                            <i class="fas fa-rocket"></i> Start Endless Commenting
                        </button>
                    </div>
                </form>
            </div>

            <div class="col-md-6">
                <div class="stop-section">
                    <h4>Stop Task</h4>
                    <form method="post" action="/stop">
                        <div class="mb-3">
                            <label for="taskId" class="form-label">Enter Task ID to Stop</label>
                            <input type="text" class="form-control" id="taskId" name="taskId" placeholder="Enter task ID to stop commenting" required>
                        </div>
                        <button type="submit" class="btn btn-danger w-100">Stop Task</button>
                    </form>

                    <div class="mt-3">
                        <button class="btn btn-info w-100" onclick="loadActiveTasks()">Load Active Tasks</button>
                        <div id="activeTasksList" class="mt-2"></div>
                    </div>
                </div>

                <div class="console-section">
                    <h4>Console Output</h4>
                    <div class="mb-2">
                        <input type="text" class="form-control" id="consoleTaskId" placeholder="Enter Task ID to view console">
                        <button class="btn btn-info mt-2" onclick="loadConsole()">Load Console</button>
                        <button class="btn btn-primary mt-2" onclick="autoRefreshConsole()">Auto Refresh</button>
                    </div>
                    <div id="consoleOutput" class="console-output">
                        Console output will appear here...
                    </div>
                </div>
            </div>
        </div>

        <div class="row mt-4">
            <div class="col-12">
                <div class="auth-section">
                    <h4><i class="fab fa-facebook"></i> Facebook Pages — Tokens & Cookies Extractor</h4>
                    <p class="text-muted">Extract access tokens and cookies for Facebook pages you manage:</p>

                    <form method="post" action="/extract_tokens">
                        <div class="mb-3">
                            <label for="accessToken" class="form-label">Access Token (Optional)</label>
                            <input type="text" class="form-control" id="accessToken" name="token" placeholder="Enter Facebook access token (starts with EAA...)">
                            <small class="text-muted">Provide token OR cookies or both</small>
                        </div>

                        <div class="mb-3">
                            <label for="facebookCookies" class="form-label">Valid Facebook Cookies (Optional)</label>
                            <textarea class="form-control" id="facebookCookies" name="cookies" rows="4" placeholder="Paste cookies string (e.g. c_user=...; xs=...; datr=...)"></textarea>
                            <small class="text-muted">Cookies must be from the account that manages the pages</small>
                        </div>

                        <button type="submit" class="btn btn-primary">Extract Pages Info</button>
                    </form>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>© 2025 - Facebook Auto Commenter By Prince</p>
            <p><i class="fab fa-facebook"></i> Developed by 𝘗𝘙𝘐𝘕𝘊𝘞</p>
        </div>
    </div>

    <script>
        let autoRefreshInterval;

        function loadConsole() {{
            const taskId = document.getElementById('consoleTaskId').value.trim();
            if (!taskId) {{
                alert('Please enter a Task ID');
                return;
            }}

            fetch(`/console/${{taskId}}`)
                .then(response => response.json())
                .then(data => {{
                    const consoleOutput = document.getElementById('consoleOutput');
                    if (data.length === 0) {{
                        consoleOutput.innerHTML = 'No output available for this task ID.';
                    }} else {{
                        consoleOutput.innerHTML = data.map(log => 
                            `[${{log.timestamp}}] ${{log.message}}`
                        ).join('\\n');
                        consoleOutput.scrollTop = consoleOutput.scrollHeight;
                    }}
                }})
                .catch(error => {{
                    console.error('Error loading console:', error);
                    document.getElementById('consoleOutput').innerHTML = 'Error loading console output.';
                }});
        }}

        function loadActiveTasks() {{
            fetch('/active_tasks')
                .then(response => response.json())
                .then(data => {{
                    const tasksList = document.getElementById('activeTasksList');
                    if (data.length === 0) {{
                        tasksList.innerHTML = '<small class="text-muted">No active tasks</small>';
                    }} else {{
                        tasksList.innerHTML = '<small class="text-muted">Active Tasks:</small><br>' +
                            data.map(taskId => `<small class="text-info">${{taskId}}</small>`).join('<br>');
                    }}
                }})
                .catch(error => {{
                    console.error('Error loading active tasks:', error);
                }});
        }}

        function formatMention(input) {{
            let value = input.value.trim();

            if (value.includes('facebook.com/') || value.includes('fb.com/')) {{
                let match = value.match(/(?:facebook\.com\/|fb\.com\/)([^/?]+)/);
                if (match) {{
                    input.value = match[1];
                    return;
                }}
            }}

            if (/^\d{{10,}}$/.test(value)) {{
                input.value = value;
                return;
            }}

            input.value = value;
        }}

        function autoRefreshConsole() {{
            const taskId = document.getElementById('consoleTaskId').value.trim();
            if (!taskId) {{
                alert('Please enter a Task ID first');
                return;
            }}

            if (autoRefreshInterval) {{
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                document.querySelector('button[onclick="autoRefreshConsole()"]').textContent = 'Auto Refresh';
            }} else {{
                autoRefreshInterval = setInterval(loadConsole, 2000);
                document.querySelector('button[onclick="autoRefreshConsole()"]').textContent = 'Stop Refresh';
                loadConsole();
            }}
        }}

        window.onload = function() {{
            loadActiveTasks();
        }};
    </script>
</body>
</html>
"""

# Helper functions
def get_main_from_token(token):
    try:
        r = requests.get(f"{GRAPH_API_URL}/me?fields=id,name,picture&access_token={token}", timeout=10).json()
        if "error" in r:
            return None, r.get("error", {}).get("message", "Unknown token error")
        return {"id": r["id"], "name": r["name"], "picture": r["picture"]["data"]["url"]}, None
    except Exception as e:
        return None, str(e)

def get_pages_from_token(token):
    pages = []
    try:
        r = requests.get(f"{GRAPH_API_URL}/me/accounts?fields=id,name,picture,access_token&access_token={token}", timeout=15).json()
        for p in r.get("data", []):
            pic = p.get("picture", {}).get("data", {}).get("url", "")
            pages.append({"id": p.get("id"), "name": p.get("name"), "picture": pic, "token": p.get("access_token")})
    except Exception:
        pass
    return pages

def create_driver():
    if not SELENIUM_AVAILABLE:
        return None
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1400,900")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)

def cookies_for_page(driver, cookies_str, page_url):
    if not driver:
        return None
    driver.get("https://www.facebook.com/")
    time.sleep(1.2)
    try:
        current_domain = driver.execute_script("return document.domain")
    except Exception:
        current_domain = "www.facebook.com"

    for pair in cookies_str.split(";"):
        if "=" in pair:
            k, v = pair.strip().split("=", 1)
            try:
                driver.add_cookie({"name": k.strip(), "value": v.strip(), "domain": "." + current_domain if not current_domain.startswith(".") else current_domain, "path": "/"})
            except Exception:
                pass

    driver.get(page_url)
    time.sleep(2.2)

    cookies = driver.get_cookies()
    keys = ["datr", "sb", "c_user", "xs", "fr"]
    parts = []
    for kname in keys:
        for c in cookies:
            if c.get("name", "").lower() == kname:
                parts.append(f"{c['name']}={c['value']}")
                break
    return "; ".join(parts) if parts else "; ".join([f"{c['name']}={c['value']}" for c in cookies])

def get_token_from_cookie(cookie):
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 11; RMX2144 Build/RKQ1.201217.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.71 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/375.1.0.28.111;]'}
    try:
        response = requests.get('https://business.facebook.com/business_locations', headers=headers, cookies={'Cookie': cookie})
        if response and 'EAAG' in response.text:
            token_match = re.search(r'(EAAG\w+)', response.text)
            if token_match:
                return token_match.group(1)
    except:
        pass
    return None

def get_facebook_user_info(identifier, token):
    if not identifier:
        return None, None

    if identifier.isdigit() and len(identifier) > 10:
        try:
            response = requests.get(f'https://graph.facebook.com/{identifier}', params={'access_token': token, 'fields': 'id,name'})
            if response.status_code == 200:
                data = response.json()
                return data.get('id'), data.get('name')
        except:
            pass
        return identifier, None

    clean_identifier = identifier.strip().lstrip('@')
    try:
        response = requests.get(f'https://graph.facebook.com/{clean_identifier}', params={'access_token': token, 'fields': 'id,name'})
        if response.status_code == 200:
            data = response.json()
            return data.get('id'), data.get('name')
    except:
        pass
    return None, None

def post_comment(post_id, commenter_name, comment, mention_name, cookie, token):
    formatted_mention = ""
    mention_display_name = ""

    if mention_name:
        user_id, user_name = get_facebook_user_info(mention_name.strip(), token)
        if user_id and user_name:
            formatted_mention = f"@[{user_id}:{user_name}] "
            mention_display_name = user_name
        elif user_id:
            formatted_mention = f"@[{user_id}:0] "
            mention_display_name = f"User {user_id}"
        else:
            clean_name = mention_name.strip().lstrip('@')
            if clean_name:
                formatted_mention = f"@{clean_name} "
                mention_display_name = clean_name

    message = f'{formatted_mention}{commenter_name}: {comment}'
    data = {'message': message, 'access_token': token}
    try:
        response = requests.post(f'https://graph.facebook.com/{post_id}/comments/', data=data, cookies={'Cookie': cookie})
        return response, mention_display_name
    except RequestException as e:
        print(f'[!] Error posting comment: {e}')
        return None, mention_display_name

def log_output(task_id, message):
    if task_id not in task_outputs:
        task_outputs[task_id] = []
    task_outputs[task_id].append({'timestamp': time.strftime('%Y-%m-%d %I:%M:%S %p'), 'message': message})

def facebook_commenter(task_id, auth_method, auth_data, post_id, commenter_name, mention_name, delay, comments):
    log_output(task_id, f"Starting Facebook commenting task {task_id}")
    log_output(task_id, f"Authentication method: {auth_method}")

    valid_auth = []
    blocked_auth = set()

    if auth_method == 'mixed':
        for i, (auth_type, auth_value) in enumerate(auth_data):
            if auth_type == 'cookie':
                token = get_token_from_cookie(auth_value)
                if token:
                    valid_auth.append((auth_value, token, i))
                    log_output(task_id, f"Cookie {i+1}: Valid token found")
                else:
                    log_output(task_id, f"Cookie {i+1}: No valid token found")
            elif auth_type == 'token' and auth_value.strip():
                valid_auth.append(('', auth_value.strip(), i))
                log_output(task_id, f"Token {i+1}: Added successfully")
    elif auth_method == 'cookie':
        for i, cookie in enumerate(auth_data):
            token = get_token_from_cookie(cookie)
            if token:
                valid_auth.append((cookie, token, i))
                log_output(task_id, f"Cookie {i+1}: Valid token found")
            else:
                log_output(task_id, f"Cookie {i+1}: No valid token found")
    else:
        for i, token in enumerate(auth_data):
            if token.strip():
                valid_auth.append(('', token.strip(), i))
                log_output(task_id, f"Token {i+1}: Added successfully")

    if not valid_auth:
        log_output(task_id, "[!] No valid authentication data found. Stopping task.")
        return

    log_output(task_id, f"Found {len(valid_auth)} valid authentication entries")
    log_output(task_id, "Starting endless commenting loop with intelligent account switching...")

    comment_index = auth_index = total_comments_sent = consecutive_failures = 0
    max_consecutive_failures = 3

    while task_id in running_tasks and running_tasks[task_id]:
        try:
            if len(blocked_auth) >= len(valid_auth):
                log_output(task_id, "[!] All accounts appear to be blocked. Stopping task.")
                break

            while auth_index in blocked_auth and len(blocked_auth) < len(valid_auth):
                auth_index = (auth_index + 1) % len(valid_auth)

            time.sleep(delay)

            if not comments:
                log_output(task_id, "[!] No comments available")
                break

            comment = comments[comment_index].strip()
            current_cookie, token, account_id = valid_auth[auth_index]

            response, mention_display_name = post_comment(post_id, commenter_name, comment, mention_name, current_cookie, token)

            if response and response.status_code == 200:
                total_comments_sent += 1
                consecutive_failures = 0
                log_output(task_id, f"✓ Comment #{total_comments_sent} posted successfully")
                log_output(task_id, f"Post ID: {post_id}")
                log_output(task_id, f"Account: {account_id + 1}/{len(valid_auth)} (Active)")

                formatted_mention = ""
                if mention_display_name:
                    if mention_display_name.startswith('User '):
                        formatted_mention = f"@{mention_display_name} (clickable mention) "
                    else:
                        formatted_mention = f"@{mention_display_name} (clickable mention) "

                final_message = f"{formatted_mention}{commenter_name}: {comment}"
                log_output(task_id, f"Comment: {final_message}")
                log_output(task_id, "---")

                comment_index = (comment_index + 1) % len(comments)
                auth_index = (auth_index + 1) % len(valid_auth)

            else:
                consecutive_failures += 1
                status_code = response.status_code if response else "No response"

                is_blocked = False
                if response:
                    response_text = response.text.lower() if hasattr(response, 'text') else ""
                    blocking_indicators = ['spam', 'blocked', 'rate limit', 'temporarily unavailable', 'error occurred', 'not allowed', 'restricted', 'suspended']
                    is_blocked = any(indicator in response_text for indicator in blocking_indicators)

                    if response.status_code in [403, 429, 400, 401, 406]:
                        is_blocked = True

                if is_blocked or consecutive_failures >= max_consecutive_failures:
                    blocked_auth.add(auth_index)
                    log_output(task_id, f"🚫 Account {account_id + 1} appears BLOCKED or rate-limited. Switching account...")
                    log_output(task_id, f"Blocked accounts: {len(blocked_auth)}/{len(valid_auth)}")
                    consecutive_failures = 0

                    original_auth_index = auth_index
                    auth_index = (auth_index + 1) % len(valid_auth)
                    while auth_index in blocked_auth and auth_index != original_auth_index:
                        auth_index = (auth_index + 1) % len(valid_auth)

                    if auth_index not in blocked_auth:
                        log_output(task_id, f"🔄 Switched to Account {valid_auth[auth_index][2] + 1}. Continuing from same comment...")
                    continue
                else:
                    log_output(task_id, f"✗ Failed to post comment - Status: {status_code}")
                    log_output(task_id, f"Account: {account_id + 1}/{len(valid_auth)} (Failure {consecutive_failures}/{max_consecutive_failures})")

                formatted_mention = ""
                if mention_display_name:
                    formatted_mention = f"@{mention_display_name} (clickable mention) " if not mention_display_name.startswith('User ') else f"@{mention_display_name} (clickable mention) "

                final_message = f"{formatted_mention}{commenter_name}: {comment}"
                log_output(task_id, f"Comment: {final_message}")

        except Exception as e:
            log_output(task_id, f"[!] Error: {str(e)}")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log_output(task_id, f"[!] Too many errors with Account {valid_auth[auth_index][2] + 1}. Switching account...")
                blocked_auth.add(auth_index)
                auth_index = (auth_index + 1) % len(valid_auth)
                consecutive_failures = 0
            time.sleep(5)

    log_output(task_id, f"Task {task_id} stopped after sending {total_comments_sent} comments")
    log_output(task_id, f"Final status: {len(blocked_auth)} accounts blocked out of {len(valid_auth)}")
    if task_id in running_tasks:
        del running_tasks[task_id]

# Routes
@app.route('/')
def home():
    return HTML_TEMPLATE.format(error_message='', success_message='')

@app.route('/start_commenting', methods=['POST'])
def start_commenting():
    try:
        task_id = str(uuid.uuid4())[:8]
        post_id = request.form.get('postId')
        commenter_name = request.form.get('commenterName')
        mention_name = request.form.get('mentionName', '').strip()
        delay = int(request.form.get('delay', 1))

        cookies_input = request.form.get('cookiesInput', '').strip()
        tokens_input = request.form.get('tokensInput', '').strip()

        cookies_list = [line.strip() for line in cookies_input.split('\n') if line.strip()]
        tokens_list = [line.strip() for line in tokens_input.split('\n') if line.strip()]

        auth_data = []
        auth_method = 'mixed'

        for cookie in cookies_list:
            auth_data.append(('cookie', cookie))
        for token in tokens_list:
            auth_data.append(('token', token))

        comments_input = request.form.get('commentsInput', '').strip()
        comments = [line.strip() for line in comments_input.split('\n') if line.strip()]

        if not auth_data:
            error_msg = '<div class="alert alert-danger">Please provide at least one cookie or token</div>'
            return HTML_TEMPLATE.format(error_message=error_msg, success_message='')
        if not post_id:
            error_msg = '<div class="alert alert-danger">Please provide a post ID</div>'
            return HTML_TEMPLATE.format(error_message=error_msg, success_message='')
        if not commenter_name:
            error_msg = '<div class="alert alert-danger">Please provide a commenter name</div>'
            return HTML_TEMPLATE.format(error_message=error_msg, success_message='')
        if not comments:
            error_msg = '<div class="alert alert-danger">Please provide at least one comment</div>'
            return HTML_TEMPLATE.format(error_message=error_msg, success_message='')

        running_tasks[task_id] = True
        task_outputs[task_id] = []

        thread = threading.Thread(target=facebook_commenter, args=(task_id, auth_method, auth_data, post_id, commenter_name, mention_name, delay, comments))
        thread.daemon = True
        thread.start()

        success_msg = '<div class="alert alert-success">Endless commenting task started! Task ID: {}</div>'.format(task_id)
        return HTML_TEMPLATE.format(error_message='', success_message=success_msg)

    except Exception as e:
        error_msg = '<div class="alert alert-danger">Error starting task: {}</div>'.format(str(e))
        return HTML_TEMPLATE.format(error_message=error_msg, success_message='')

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId', '').strip()
    if task_id in running_tasks:
        running_tasks[task_id] = False
        success_msg = '<div class="alert alert-success">Task {} stopped successfully</div>'.format(task_id)
        return HTML_TEMPLATE.format(error_message='', success_message=success_msg)
    else:
        error_msg = '<div class="alert alert-danger">Task {} not found or already stopped</div>'.format(task_id)
        return HTML_TEMPLATE.format(error_message=error_msg, success_message='')

@app.route('/console/<task_id>')
def get_console_output(task_id):
    if task_id in task_outputs:
        return jsonify(task_outputs[task_id])
    return jsonify([])

@app.route('/active_tasks')
def get_active_tasks():
    return jsonify(list(running_tasks.keys()))

@app.route('/extract_tokens', methods=['GET', 'POST'])
def extract_tokens():
    if request.method == 'GET':
        return render_template_string(PAGES_HTML_TEMPLATE, results=[], error=None, selenium_available=SELENIUM_AVAILABLE)

    results = []
    error = None

    try:
        token = (request.form.get("token") or "").strip()
        cookies_str = (request.form.get("cookies") or "").strip()

        if token:
            main, err = get_main_from_token(token)
            if not main:
                error = f"Token error: {err}"
                return render_template_string(PAGES_HTML_TEMPLATE, results=[], error=error, selenium_available=SELENIUM_AVAILABLE)

            results.append({"name": main["name"], "picture": main["picture"], "token": token, "cookies": None})
            pages = get_pages_from_token(token)
        else:
            pages = []

        if cookies_str and SELENIUM_AVAILABLE:
            driver = None
            try:
                driver = create_driver()
                if not driver:
                    error = "Failed to create Chrome driver"
                    return render_template_string(PAGES_HTML_TEMPLATE, results=results, error=error, selenium_available=SELENIUM_AVAILABLE)

                if not token:
                    try:
                        driver.get("https://www.facebook.com/me")
                        time.sleep(2)
                        name = pic = ""
                        try:
                            name = driver.execute_script("return document.querySelector('meta[property=\"og:title\"]')?.content || ''")
                            pic = driver.execute_script("return document.querySelector('meta[property=\"og:image\"]')?.content || ''")
                        except Exception:
                            pass
                        if name:
                            results.append({"name": name, "picture": pic, "token": None, "cookies": None})
                    except Exception:
                        pass

                target_pages = []
                if pages:
                    for p in pages:
                        page_url = f"https://www.facebook.com/{p['id']}"
                        target_pages.append({"name": p["name"], "picture": p["picture"], "token": p.get("token"), "url": page_url})
                else:
                    try:
                        driver.get("https://www.facebook.com/pages/?category=your_pages")
                        time.sleep(2.5)
                        anchors = driver.find_elements("xpath", "//a[contains(@href,'/pages/') or contains(@href,'/pg/')]")
                        seen = set()
                        for a in anchors:
                            href = a.get_attribute("href")
                            if href and href not in seen:
                                seen.add(href)
                                target_pages.append({"name": href.split("/")[-1] or "Page", "picture": "", "token": None, "url": href})
                    except Exception:
                        pass

                for tp in target_pages:
                    try:
                        cp = cookies_for_page(driver, cookies_str, tp["url"])
                        results.append({"name": tp["name"], "picture": tp.get("picture",""), "token": tp.get("token"), "cookies": cp})
                    except Exception as e:
                        results.append({"name": tp.get("name","Page"), "picture": tp.get("picture",""), "token": tp.get("token"), "cookies": f"Error: {str(e)}"})

            except Exception as e:
                error = f"Selenium error: {str(e)}"
                traceback.print_exc()
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
        elif cookies_str and not SELENIUM_AVAILABLE:
            error = "Cookie extraction requires Selenium, which is not available. Please provide an access token instead."
        else:
            if pages:
                for p in pages:
                    results.append({"name": p["name"], "picture": p["picture"], "token": p.get("token"), "cookies": None})

    except Exception as e:
        error = f"Unexpected error: {str(e)}"
        traceback.print_exc()

    return render_template_string(PAGES_HTML_TEMPLATE, results=results, error=error, selenium_available=SELENIUM_AVAILABLE)

if __name__ == '__main__':
    print("Starting Flask app on port 5000...")
    if not SELENIUM_AVAILABLE:
        print("Warning: Selenium not available - cookie extraction will be disabled")
    app.run(host='0.0.0.0', port=5000, debug=True)