import google.generativeai as genai
import PIL.Image
import io
import os
import socket
import datetime
import threading
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for

# ═══════════════════════════════════════════════════════════════
#   SETTINGS
# ═══════════════════════════════════════════════════════════════
API_KEY = os.environ.get("GEMINI_API_KEY")
PORT       = int(os.environ.get("PORT", 5000))
SECRET_KEY = os.environ.get("SECRET_KEY", "classsnap-secret-xyz")
# ═══════════════════════════════════════════════════════════════

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "gif", "tiff"}

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("models/gemini-flash-latest")

# In-memory store of all extracted results (for dashboard display)
extracted_results = []
photo_count = [0]
lock = threading.Lock()


# ════════════════════════════════════════════════════════════════
#   DIRECT EXTRACT — image bytes → Gemini → stored in memory
# ════════════════════════════════════════════════════════════════
def extract_from_bytes(image_bytes, original_filename):
    photo_count[0] += 1
    count = photo_count[0]

    print(f"\n{'='*50}")
    print(f"  Photo #{count}: {original_filename}")
    print(f"  Sending to Gemini...")

    try:
        image = PIL.Image.open(io.BytesIO(image_bytes))

        response = model.generate_content([
            image,
            """This is a photo of code on a classroom screen or whiteboard.
Please:
1. Extract ALL visible code exactly, preserve indentation and syntax
2. Fix distorted characters (0 vs O, 1 vs l, ; vs :)
3. Identify the programming language
4. Give a short code review — errors, missing parts, one beginner tip

Format response as:
# ── Photo: [filename] ──────────────────────────────
# Language: [language]

[extracted code here — no markdown, just raw code]

# Code Review:
# [review points here, each as a comment]
# ────────────────────────────────────────────────────
"""
        ])

        result = response.text
        result = result.replace("```python", "").replace("```", "").strip()

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        with lock:
            extracted_results.insert(0, {
                "count":    count,
                "filename": original_filename,
                "time":     timestamp,
                "code":     result
            })

        print(f"  ✓ Code extracted — stored in dashboard")
        return True, result

    except Exception as e:
        print(f"  ERROR: {e}")
        with lock:
            extracted_results.insert(0, {
                "count":    count,
                "filename": original_filename,
                "time":     datetime.datetime.now().strftime("%H:%M:%S"),
                "code":     f"# ERROR: {str(e)}"
            })
        return False, str(e)


# ════════════════════════════════════════════════════════════════
#   HTML PAGES
# ════════════════════════════════════════════════════════════════
HOME_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Snap2Code</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f3460 100%);
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center; padding: 2rem 1rem;
    }
    .logo { font-size: 3.5rem; margin-bottom: 0.75rem; }
    h1 { font-size: 2rem; font-weight: 700; color: #fff; margin-bottom: 0.3rem; }
    p.tagline { font-size: 0.9rem; color: #94a3b8; margin-bottom: 3rem; text-align: center; }
    .btn-group { display: flex; flex-direction: column; gap: 1rem; width: 100%; max-width: 300px; }
    .btn {
      display: block; width: 100%; padding: 1rem 1.5rem;
      border-radius: 14px; font-size: 1rem; font-weight: 600;
      text-align: center; text-decoration: none;
      transition: transform 0.15s;
    }
    .btn:active { transform: scale(0.97); }
    .btn-green { background: #1d9e75; color: white; }
    .btn-green:hover { background: #0f6e56; }
    .btn-outline { background: transparent; color: #fff; border: 1.5px solid rgba(255,255,255,0.25); }
    .btn-outline:hover { border-color: #fff; background: rgba(255,255,255,0.05); }
    .hint { margin-top: 2.5rem; font-size: 0.75rem; color: #475569; text-align: center; }
  </style>
</head>
<body>
  <div class="logo">📸</div>
  <h1>Snap2Code</h1>
  <p class="tagline">Snap a photo of classroom code.<br>Get clean, executable code instantly.</p>
  <div class="btn-group">
    <a href="/login" class="btn btn-green">🔐  Login</a>
    <a href="/dashboard" class="btn btn-outline">📊  Dashboard</a>
  </div>
  <p class="hint">Dashboard requires login — both buttons are safe to tap</p>
</body>
</html>"""


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login — Snap2Code</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f3460 100%);
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center; padding: 1rem;
    }
    .card { background: white; border-radius: 22px; padding: 2.25rem 1.75rem; width: 100%; max-width: 380px; }
    .logo { font-size: 2.2rem; text-align: center; margin-bottom: 0.5rem; }
    h1 { font-size: 1.4rem; font-weight: 700; text-align: center; color: #1a1a1a; margin-bottom: 0.25rem; }
    p.sub { font-size: 0.85rem; color: #888; text-align: center; margin-bottom: 1.75rem; }
    label { display: block; font-size: 0.78rem; font-weight: 600; color: #555; margin-bottom: 0.3rem; margin-top: 1rem; }
    input[type=text], input[type=password] {
      width: 100%; padding: 0.8rem 1rem;
      border: 1.5px solid #e2e8f0; border-radius: 10px;
      font-size: 1rem; outline: none; color: #1a1a1a; transition: border-color 0.2s;
    }
    input:focus { border-color: #1d9e75; }
    .btn-login {
      display: block; width: 100%; padding: 0.9rem;
      background: #1d9e75; color: white; font-size: 1rem; font-weight: 600;
      border: none; border-radius: 12px; cursor: pointer; margin-top: 1.5rem;
    }
    .btn-login:hover { background: #0f6e56; }
    .back { display: block; text-align: center; margin-top: 1.1rem; font-size: 0.85rem; color: #aaa; text-decoration: none; }
    .back:hover { color: #1d9e75; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🔐</div>
    <h1>Welcome back</h1>
    <p class="sub">Enter any username &amp; password to continue</p>
    <form method="POST" action="/login">
      <label>USERNAME</label>
      <input type="text" name="username" placeholder="e.g. judge1" required>
      <label>PASSWORD</label>
      <input type="password" name="password" placeholder="any password" required>
      <button type="submit" class="btn-login">Login →</button>
    </form>
    <a href="/" class="back">← Back to home</a>
  </div>
</body>
</html>"""


DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard — Snap2Code</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0fdf8;
      display: flex; flex-direction: column;
      align-items: center; min-height: 100vh; padding: 0 1rem 3rem;
    }
    .topbar {
      width: 100%; max-width: 700px;
      display: flex; align-items: center; justify-content: space-between;
      padding: 1.25rem 0 1rem;
    }
    .brand { display: flex; align-items: center; gap: 8px; }
    .brand span { font-size: 1.3rem; }
    .brand h2 { font-size: 1rem; font-weight: 700; color: #1a1a1a; }
    .right-group { display: flex; gap: 8px; align-items: center; }
    .user-chip { font-size: 0.75rem; background: #1d9e75; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; }
    .logout { font-size: 0.75rem; color: #888; text-decoration: none; padding: 4px 10px; border: 1px solid #ddd; border-radius: 20px; }
    .logout:hover { color: #e24b4a; border-color: #fca5a5; }

    .status-pill {
      width: 100%; max-width: 700px;
      background: #d1fae5; border: 1px solid #6ee7b7; border-radius: 10px;
      padding: 0.55rem 1rem; display: flex; align-items: center; gap: 8px;
      font-size: 0.83rem; color: #065f46; margin-bottom: 1.25rem;
    }
    .dot { width: 8px; height: 8px; background: #10b981; border-radius: 50%; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

    .layout { display: flex; gap: 1rem; width: 100%; max-width: 700px; align-items: flex-start; }

    /* left panel — upload */
    .upload-panel {
      background: white; border-radius: 18px; padding: 1.4rem;
      width: 260px; flex-shrink: 0;
      box-shadow: 0 2px 14px rgba(0,0,0,0.06);
    }

    /* right panel — results */
    .results-panel {
      background: white; border-radius: 18px; padding: 1.4rem;
      flex: 1; box-shadow: 0 2px 14px rgba(0,0,0,0.06);
      min-height: 300px;
    }

    .card-title { font-size: 0.82rem; font-weight: 700; color: #64748b; margin-bottom: 1rem; letter-spacing: 0.4px; }

    .pick-btn {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      width: 100%; padding: 0.85rem; border-radius: 12px;
      font-size: 0.9rem; font-weight: 500; cursor: pointer;
      border: 2px dashed #cbd5e1; background: #f8fafc; color: #334155;
      margin-bottom: 0.65rem; transition: border-color 0.2s;
    }
    .pick-btn:hover { border-color: #1d9e75; background: #f0fdf8; }
    input[type=file] { display: none; }

    #preview-wrap { display: none; margin-bottom: 0.75rem; text-align: center; }
    #preview { max-width: 100%; max-height: 180px; border-radius: 8px; }
    #file-name { font-size: 0.72rem; color: #94a3b8; margin-top: 4px; }

    #send-btn {
      display: none; width: 100%; padding: 0.8rem;
      background: #1d9e75; color: white; font-size: 0.95rem; font-weight: 600;
      border: none; border-radius: 12px; cursor: pointer;
    }
    #send-btn:disabled { background: #94a3b8; cursor: default; }

    #status { margin-top: 0.65rem; font-size: 0.85rem; text-align: center; min-height: 1.3em; }
    .ok  { color: #1d9e75; font-weight: 600; }
    .err { color: #e24b4a; font-weight: 600; }
    .processing { color: #f59e0b; font-weight: 600; }

    /* code result cards */
    .result-card {
      border: 1px solid #bbf7d0; border-radius: 10px;
      margin-bottom: 1rem; overflow: hidden;
    }
    .result-header {
      background: #f0fdf8; padding: 0.5rem 0.75rem;
      display: flex; justify-content: space-between; align-items: center;
    }
    .result-header span { font-size: 0.78rem; font-weight: 600; color: #065f46; }
    .result-header small { font-size: 0.72rem; color: #94a3b8; }
    pre {
      background: #0f172a; color: #e2e8f0;
      padding: 0.75rem; font-size: 0.78rem;
      overflow-x: auto; white-space: pre-wrap; word-break: break-word;
      margin: 0; max-height: 300px; overflow-y: auto;
    }
    .copy-btn {
      background: #1d9e75; color: white; border: none;
      font-size: 0.72rem; padding: 3px 10px; border-radius: 6px;
      cursor: pointer; font-weight: 600;
    }
    .empty { font-size: 0.85rem; color: #94a3b8; text-align: center; padding: 2rem 0; }

    @media (max-width: 560px) {
      .layout { flex-direction: column; }
      .upload-panel { width: 100%; }
    }
  </style>
</head>
<body>

  <div class="topbar">
    <div class="brand"><span>📸</span><h2>Snap2Code</h2></div>
    <div class="right-group">
      <span class="user-chip">{{ username }}</span>
      <a href="/logout" class="logout">Logout</a>
    </div>
  </div>

  <div class="status-pill">
    <div class="dot"></div>
    Live — photo sent directly to Gemini AI, extracted code shown instantly below
  </div>

  <div class="layout">

    <!-- Upload panel -->
    <div class="upload-panel">
      <p class="card-title">📤 SEND A PHOTO</p>
      <label class="pick-btn" for="cam-input">📷  Camera</label>
      <input type="file" id="cam-input" accept="image/*" capture="environment">
      <label class="pick-btn" for="gal-input">🖼️  Gallery</label>
      <input type="file" id="gal-input" accept="image/*">
      <div id="preview-wrap">
        <img id="preview" alt="preview">
        <div id="file-name"></div>
      </div>
      <button id="send-btn">⚡ Extract Code</button>
      <div id="status"></div>
    </div>

    <!-- Results panel -->
    <div class="results-panel">
      <p class="card-title">💻 EXTRACTED CODE</p>
      <div id="results-area">
        <p class="empty">Send a photo to see extracted code here</p>
      </div>
    </div>

  </div>

<script>
  let selectedFile = null;
  let firstResult = true;

  function pickFile(file) {
    if (!file) return;
    selectedFile = file;
    document.getElementById('preview').src = URL.createObjectURL(file);
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('preview-wrap').style.display = 'block';
    document.getElementById('send-btn').style.display = 'block';
    document.getElementById('status').textContent = '';
  }

  document.getElementById('cam-input').addEventListener('change', e => pickFile(e.target.files[0]));
  document.getElementById('gal-input').addEventListener('change', e => pickFile(e.target.files[0]));

  document.getElementById('send-btn').addEventListener('click', async () => {
    if (!selectedFile) return;
    const btn = document.getElementById('send-btn');
    const status = document.getElementById('status');
    btn.disabled = true;
    btn.textContent = 'Extracting…';
    status.innerHTML = '<span class="processing">⏳ Gemini is reading...</span>';

    const fd = new FormData();
    fd.append('image', selectedFile);

    try {
      const res = await fetch('/upload', { method: 'POST', body: fd });
      const data = await res.json();
      if (data.ok) {
        status.innerHTML = '<span class="ok">✓ Done!</span>';
        showResult(selectedFile.name, data.code, data.time);
        selectedFile = null;
        document.getElementById('preview-wrap').style.display = 'none';
        btn.style.display = 'none';
        document.getElementById('cam-input').value = '';
        document.getElementById('gal-input').value = '';
      } else {
        status.innerHTML = '<span class="err">Error: ' + data.error + '</span>';
      }
    } catch {
      status.innerHTML = '<span class="err">Could not reach server</span>';
    }
    btn.disabled = false;
    btn.textContent = '⚡ Extract Code';
  });

  function showResult(filename, code, time) {
    const area = document.getElementById('results-area');
    if (firstResult) { area.innerHTML = ''; firstResult = false; }

    const card = document.createElement('div');
    card.className = 'result-card';
    const id = 'code-' + Date.now();
    card.innerHTML = `
      <div class="result-header">
        <span>📄 ${filename}</span>
        <div style="display:flex;gap:8px;align-items:center">
          <small>${time}</small>
          <button class="copy-btn" onclick="copyCode('${id}')">Copy</button>
        </div>
      </div>
      <pre id="${id}">${escHtml(code)}</pre>
    `;
    area.prepend(card);
  }

  function copyCode(id) {
    const text = document.getElementById(id).textContent;
    navigator.clipboard.writeText(text).then(() => {
      event.target.textContent = 'Copied!';
      setTimeout(() => event.target.textContent = 'Copy', 1500);
    });
  }

  function escHtml(t) {
    return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════════
#   FLASK ROUTES
# ════════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def is_logged_in():
    return session.get("logged_in") is True


@app.route("/")
def home():
    return render_template_string(HOME_PAGE)


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if u and p:
            session["logged_in"] = True
            session["username"] = u
            return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_PAGE)


@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template_string(DASHBOARD_PAGE, username=session.get("username", "user"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/upload", methods=["POST"])
def upload():
    if not is_logged_in():
        return jsonify(ok=False, error="Not logged in"), 401
    if "image" not in request.files:
        return jsonify(ok=False, error="No file received")
    f = request.files["image"]
    if f.filename == "" or not allowed(f.filename):
        return jsonify(ok=False, error="Invalid file type")

    image_bytes = f.read()
    original_filename = f.filename

    # Process synchronously so we can return the code to the browser
    success, result = extract_from_bytes(image_bytes, original_filename)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    if success:
        return jsonify(ok=True, code=result, time=timestamp)
    else:
        return jsonify(ok=False, error=result)


# ════════════════════════════════════════════════════════════════
#   MAIN
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"

    print("=" * 50)
    print("   Snap2Code — Deploy Ready")
    print("=" * 50)
    print(f"  Local URL : http://{ip}:{PORT}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=PORT, debug=False)
