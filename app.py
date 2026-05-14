#!/usr/bin/env python3
"""
Web UI: ChatGPT text (with LaTeX) → Word → download / upload to web
Run: python3 app.py
Then open: http://localhost:5000
"""

import os, re, tempfile, subprocess, warnings
warnings.filterwarnings("ignore")

from flask import Flask, request, render_template_string, send_file, jsonify
import requests as req

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

# ── LaTeX normalizer ────────────────────────────────────────────────────────

def normalize_latex(text: str) -> str:
    text = re.sub(r'\\\((.+?)\\\)', r'$\1$', text, flags=re.DOTALL)
    text = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    return text

# ── Convert to docx ─────────────────────────────────────────────────────────

def convert_to_docx(md_text: str) -> str:
    """Returns path to temp .docx file."""
    tmp_md = tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                         delete=False, encoding="utf-8")
    tmp_md.write(md_text)
    tmp_md.close()

    out_path = tmp_md.name.replace(".md", ".docx")
    cmd = ["pandoc", tmp_md.name, "-o", out_path,
           "--mathml", "--standalone", "--metadata", "lang=zh-TW"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(tmp_md.name)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return out_path

# ── Upload to gofile.io ─────────────────────────────────────────────────────

def upload_gofile(path: str, filename: str) -> str:
    r = req.get("https://api.gofile.io/servers", timeout=10)
    server = r.json()["data"]["servers"][0]["name"]
    r = req.post("https://api.gofile.io/accounts", timeout=10)
    token = r.json()["data"]["token"]
    with open(path, "rb") as f:
        r = req.post(
            f"https://{server}.gofile.io/contents/uploadFile",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, f,
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document")},
            timeout=60,
        )
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(str(data))
    return data["data"]["downloadPage"]

# ── HTML template ───────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ChatGPT → Word 轉換器</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f172a; color: #e2e8f0; min-height: 100vh;
    display: flex; flex-direction: column; align-items: center;
    padding: 2rem 1rem;
  }
  h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.3rem;
       background: linear-gradient(90deg,#60a5fa,#a78bfa); -webkit-background-clip:text;
       -webkit-text-fill-color:transparent; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1.8rem; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px;
          padding: 1.5rem; width: 100%; max-width: 820px; }
  label { display: block; font-size: 0.85rem; color: #94a3b8;
          margin-bottom: 0.4rem; margin-top: 1rem; }
  textarea {
    width: 100%; height: 340px; background: #0f172a; color: #e2e8f0;
    border: 1px solid #334155; border-radius: 8px; padding: 0.8rem;
    font-family: "JetBrains Mono", "Fira Code", monospace; font-size: 0.85rem;
    resize: vertical; outline: none; transition: border-color .2s;
  }
  textarea:focus { border-color: #60a5fa; }
  .row { display: flex; gap: 0.8rem; margin-top: 1rem; align-items: center; }
  input[type=text] {
    flex: 1; background: #0f172a; color: #e2e8f0; border: 1px solid #334155;
    border-radius: 8px; padding: 0.6rem 0.8rem; font-size: 0.9rem; outline: none;
    transition: border-color .2s;
  }
  input[type=text]:focus { border-color: #60a5fa; }
  .options { display: flex; gap: 1.2rem; align-items: center; font-size: 0.88rem; }
  label.check { display: flex; align-items: center; gap: 0.4rem; cursor: pointer;
                color: #cbd5e1; margin-top: 0; }
  input[type=checkbox] { accent-color: #60a5fa; width: 15px; height: 15px; cursor: pointer; }
  button {
    background: linear-gradient(135deg,#3b82f6,#7c3aed); color: #fff;
    border: none; border-radius: 8px; padding: 0.65rem 1.6rem;
    font-size: 0.95rem; font-weight: 600; cursor: pointer;
    transition: opacity .2s, transform .1s; white-space: nowrap;
  }
  button:hover { opacity: .9; } button:active { transform: scale(.97); }
  button:disabled { opacity: .5; cursor: not-allowed; }
  #status { margin-top: 1.2rem; padding: 1rem; border-radius: 8px;
             font-size: 0.9rem; display: none; }
  #status.info  { background:#1e3a5f; border:1px solid #3b82f6; color:#93c5fd; }
  #status.ok    { background:#14532d; border:1px solid #22c55e; color:#86efac; }
  #status.error { background:#7f1d1d; border:1px solid #ef4444; color:#fca5a5; }
  .spinner { display:inline-block; width:14px; height:14px; border:2px solid #60a5fa;
             border-top-color:transparent; border-radius:50%; animation:spin .7s linear infinite;
             vertical-align:middle; margin-right:6px; }
  @keyframes spin { to { transform: rotate(360deg) } }
  .result-link { font-size: 1rem; word-break: break-all; }
  .result-link a { color: #60a5fa; }
  .dl-btn { margin-top: 0.6rem; display: inline-block; background: #166534;
             color: #86efac; border: 1px solid #22c55e; border-radius: 6px;
             padding: 0.4rem 1rem; font-size: 0.85rem; text-decoration: none;
             transition: background .2s; }
  .dl-btn:hover { background: #15803d; }
  .tip { color: #64748b; font-size: 0.8rem; margin-top: 0.5rem; }
  .badge { background: #334155; color: #94a3b8; font-size: 0.75rem;
           border-radius: 4px; padding: 2px 6px; margin-left: 4px; }
</style>
</head>
<body>
<h1>ChatGPT → Word 轉換器</h1>
<p class="subtitle">支援 Markdown + LaTeX 數學公式，一鍵轉成 .docx 並上傳至網路</p>

<div class="card">
  <label>貼上 ChatGPT 文字內容 <span class="badge">Markdown + LaTeX</span></label>
  <textarea id="content" placeholder="# 標題&#10;&#10;這是行內公式 $E = mc^2$，這是獨立公式：&#10;&#10;$$\int_0^1 x^2\,dx = \frac{1}{3}$$&#10;&#10;支援 \( f(x) \) 和 \[ ... \] 等各種 LaTeX 格式。"></textarea>

  <div class="row">
    <input type="text" id="filename" placeholder="輸出檔名（選填，例如：微積分筆記）" />
    <div class="options">
      <label class="check">
        <input type="checkbox" id="upload" checked>
        上傳至網路
      </label>
    </div>
    <button id="btn" onclick="convert()">轉換 →</button>
  </div>
  <p class="tip">不含副檔名；留空則使用「output」</p>

  <div id="status"></div>
</div>

<script>
async function convert() {
  const content = document.getElementById('content').value.trim();
  if (!content) { showStatus('請先貼上文字內容', 'error'); return; }

  const filename = (document.getElementById('filename').value.trim() || 'output')
                     .replace(/\.docx$/i, '');
  const doUpload = document.getElementById('upload').checked;
  const btn = document.getElementById('btn');
  btn.disabled = true;

  showStatus('<span class="spinner"></span>轉換中…', 'info');

  try {
    const res = await fetch('/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, filename, upload: doUpload })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '未知錯誤');

    let html = `<div class="result-link">`;
    if (data.url) {
      html += `✅ 上傳完成！<br><a href="${data.url}" target="_blank">${data.url}</a>`;
    } else {
      html += `✅ 轉換完成！`;
    }
    html += `</div>`;
    html += `<a class="dl-btn" href="/download/${data.token}">⬇ 下載 ${filename}.docx</a>`;
    showStatus(html, 'ok');
  } catch(e) {
    showStatus('❌ 錯誤：' + e.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

function showStatus(html, type) {
  const el = document.getElementById('status');
  el.innerHTML = html;
  el.className = type;
  el.style.display = 'block';
}

document.getElementById('content').addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') convert();
});
</script>
</body>
</html>
"""

# ── In-memory store for download tokens ────────────────────────────────────

import uuid, threading, time

_store: dict[str, tuple[str, str, float]] = {}  # token → (path, filename, expires)
_lock = threading.Lock()

def store_file(path: str, filename: str) -> str:
    token = uuid.uuid4().hex
    with _lock:
        _store[token] = (path, filename, time.time() + 3600)
    return token

def cleanup():
    while True:
        time.sleep(300)
        now = time.time()
        with _lock:
            expired = [t for t, (p, _, exp) in _store.items() if now > exp]
            for t in expired:
                try: os.unlink(_store[t][0])
                except: pass
                del _store[t]

threading.Thread(target=cleanup, daemon=True).start()

# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json()
    content: str = data.get("content", "")
    filename: str = data.get("filename", "output").strip() or "output"
    do_upload: bool = data.get("upload", True)

    if not content:
        return jsonify(error="內容不可為空"), 400

    try:
        md = normalize_latex(content)
        docx_path = convert_to_docx(md)
        token = store_file(docx_path, f"{filename}.docx")

        url = None
        if do_upload:
            url = upload_gofile(docx_path, f"{filename}.docx")

        return jsonify(token=token, url=url)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/download/<token>")
def download(token: str):
    with _lock:
        entry = _store.get(token)
    if not entry:
        return "連結已過期或不存在", 404
    path, filename, _ = entry
    return send_file(path, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument"
                              ".wordprocessingml.document")

if __name__ == "__main__":
    print("✓ 開啟瀏覽器前往 http://localhost:5000")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, port=port)
