#!/usr/bin/env python3
"""Ayman Termux Suite - لوحة التحكم الموحدة (Port: 7500)"""
import os, json, subprocess, signal
from datetime import datetime
from flask import Flask, render_template_string, jsonify

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "config", "apps.json")
LOGS_DIR = os.path.join(BASE, "logs")
PID_DIR = os.path.join(BASE, "logs", "pids")

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PID_DIR, exist_ok=True)

app = Flask(__name__)


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def is_running(app_id):
    pid_file = os.path.join(PID_DIR, f"{app_id}.pid")
    if not os.path.exists(pid_file):
        return False, None
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True, pid
    except (ProcessLookupError, ValueError):
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return False, None


def start_app(app_conf):
    app_id = app_conf["id"]
    path = os.path.join(BASE, app_conf["path"])
    entry = app_conf["entry"]
    if not os.path.exists(path):
        return False, f"المسار مش موجود: {app_conf['path']}"
    entry_path = os.path.join(path, entry)
    if not os.path.exists(entry_path):
        return False, f"الملف مش موجود: {entry}"
    running, pid = is_running(app_id)
    if running:
        return True, f"شغال بالفعل (PID: {pid})"
    log_file = os.path.join(LOGS_DIR, f"{app_id}.log")
    pid_file = os.path.join(PID_DIR, f"{app_id}.pid")
    try:
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"\n\n===== [{datetime.now()}] بدء التشغيل =====\n")
            proc = subprocess.Popen(
                ["python", entry], cwd=path, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
        with open(pid_file, "w") as f:
            f.write(str(proc.pid))
        return True, f"اتشغّل (PID: {proc.pid})"
    except Exception as e:
        return False, f"خطأ: {e}"


def stop_app(app_id):
    running, pid = is_running(app_id)
    if not running:
        return False, "مش شغال"
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        pid_file = os.path.join(PID_DIR, f"{app_id}.pid")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return True, "اتوقف"
    except Exception as e:
        return False, f"خطأ: {e}"


def get_status():
    cfg = load_config()
    result = []
    for a in cfg["apps"]:
        running, pid = is_running(a["id"])
        result.append({
            "id": a["id"], "name": a["name"],
            "description": a["description"], "port": a["port"],
            "running": running, "pid": pid,
            "url": f"http://localhost:{a['port']}",
            "enabled": a.get("enabled", True),
        })
    return result


HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ayman Termux Suite</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Tahoma, sans-serif; background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); min-height: 100vh; padding: 20px; color: #eee; }
  .container { max-width: 900px; margin: 0 auto; }
  header { text-align: center; padding: 30px 20px; margin-bottom: 25px; background: rgba(255,255,255,0.05); border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); }
  h1 { font-size: 1.8em; margin-bottom: 8px; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .subtitle { color: #888; font-size: 0.9em; }
  .stats { display: flex; gap: 12px; margin-top: 20px; justify-content: center; flex-wrap: wrap; }
  .stat { background: rgba(255,255,255,0.08); padding: 12px 20px; border-radius: 12px; text-align: center; min-width: 100px; }
  .stat-num { font-size: 1.8em; font-weight: 700; color: #667eea; }
  .stat-label { font-size: 0.8em; color: #888; margin-top: 4px; }
  .all-actions { display: flex; gap: 10px; margin-bottom: 20px; }
  .all-actions button { flex: 1; padding: 14px; border: none; border-radius: 12px; cursor: pointer; font-size: 1em; font-weight: 700; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; }
  .all-actions button.stop-all { background: linear-gradient(135deg, #f44336, #c62828); }
  .apps-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 700px) { .apps-grid { grid-template-columns: 1fr 1fr; } }
  .app-card { background: rgba(255,255,255,0.06); border-radius: 16px; padding: 18px; border: 1px solid rgba(255,255,255,0.1); transition: 0.3s; }
  .app-card:hover { transform: translateY(-2px); background: rgba(255,255,255,0.1); }
  .app-card.running { border-color: rgba(76,175,80,0.5); }
  .app-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px; }
  .app-name { font-size: 1.1em; font-weight: 700; color: #fff; }
  .app-status { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 0.75em; font-weight: 600; white-space: nowrap; }
  .status-running { background: rgba(76,175,80,0.2); color: #4caf50; }
  .status-stopped { background: rgba(120,120,120,0.2); color: #999; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
  .dot.pulse { animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .app-desc { color: #aaa; font-size: 0.85em; margin-bottom: 12px; min-height: 2.4em; }
  .app-port { color: #667eea; font-family: monospace; font-size: 0.8em; margin-bottom: 12px; }
  .app-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .app-actions button { flex: 1; min-width: 80px; padding: 10px; border: none; border-radius: 10px; cursor: pointer; font-size: 0.85em; font-weight: 600; transition: 0.2s; background: rgba(255,255,255,0.1); color: #fff; }
  .app-actions button:hover:not(:disabled) { background: rgba(255,255,255,0.2); }
  .btn-start { background: linear-gradient(135deg, #4caf50, #388e3c) !important; }
  .btn-stop { background: linear-gradient(135deg, #f44336, #c62828) !important; }
  .btn-open { background: linear-gradient(135deg, #667eea, #764ba2) !important; }
  .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.9); color: #fff; padding: 12px 24px; border-radius: 30px; font-size: 0.9em; display: none; z-index: 1000; }
  .toast.show { display: block; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🎛️ Ayman Termux Suite</h1>
    <p class="subtitle">لوحة التحكم الموحدة لكل التطبيقات</p>
    <div class="stats">
      <div class="stat"><div class="stat-num" id="totalCount">0</div><div class="stat-label">إجمالي</div></div>
      <div class="stat"><div class="stat-num" id="runningCount" style="color:#4caf50">0</div><div class="stat-label">شغال</div></div>
      <div class="stat"><div class="stat-num" id="stoppedCount" style="color:#999">0</div><div class="stat-label">متوقف</div></div>
    </div>
  </header>
  <div class="all-actions">
    <button onclick="startAll()">🚀 شغّل الكل</button>
    <button class="stop-all" onclick="stopAll()">🛑 وقّف الكل</button>
  </div>
  <div class="apps-grid" id="appsGrid"></div>
</div>
<div class="toast" id="toast"></div>
<script>
async function loadApps() {
  const r = await fetch('/api/status');
  const data = await r.json();
  const grid = document.getElementById('appsGrid');
  grid.innerHTML = '';
  let running = 0, stopped = 0;
  data.apps.forEach(a => {
    if (a.running) running++; else stopped++;
    const card = document.createElement('div');
    card.className = 'app-card ' + (a.running ? 'running' : 'stopped');
    card.innerHTML = `
      <div class="app-header">
        <div class="app-name">${a.name}</div>
        <div class="app-status ${a.running ? 'status-running' : 'status-stopped'}">
          <span class="dot ${a.running ? 'pulse' : ''}"></span>
          ${a.running ? 'شغال' : 'متوقف'}
        </div>
      </div>
      <div class="app-desc">${a.description}</div>
      <div class="app-port">🔌 بورت ${a.port}${a.pid ? ' • PID ' + a.pid : ''}</div>
      <div class="app-actions">
        ${a.running
          ? `<button class="btn-stop" onclick="stopApp('${a.id}')">🛑 وقّف</button>
             <button class="btn-open" onclick="window.open('${a.url}','_blank')">🌐 افتح</button>`
          : `<button class="btn-start" onclick="startApp('${a.id}')">▶️ شغّل</button>`}
      </div>
    `;
    grid.appendChild(card);
  });
  document.getElementById('totalCount').textContent = data.apps.length;
  document.getElementById('runningCount').textContent = running;
  document.getElementById('stoppedCount').textContent = stopped;
}
async function startApp(id) { showToast('⏳...'); const r = await fetch('/api/start/'+id,{method:'POST'}); const d = await r.json(); showToast(d.success ? '✅ '+d.message : '⚠️ '+d.message); setTimeout(loadApps,800); }
async function stopApp(id) { showToast('⏳...'); const r = await fetch('/api/stop/'+id,{method:'POST'}); const d = await r.json(); showToast(d.success ? '✅ '+d.message : '⚠️ '+d.message); setTimeout(loadApps,800); }
async function startAll() { showToast('⏳ جاري تشغيل الكل...'); await fetch('/api/start-all',{method:'POST'}); showToast('✅ تم'); setTimeout(loadApps,1500); }
async function stopAll() { if(!confirm('متأكد؟')) return; showToast('⏳...'); await fetch('/api/stop-all',{method:'POST'}); showToast('✅ تم'); setTimeout(loadApps,1500); }
function showToast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(window._t); window._t = setTimeout(()=>t.classList.remove('show'), 2500); }
loadApps(); setInterval(loadApps, 5000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/status")
def api_status():
    return jsonify({"apps": get_status()})


@app.route("/api/start/<app_id>", methods=["POST"])
def api_start(app_id):
    cfg = load_config()
    app_conf = next((a for a in cfg["apps"] if a["id"] == app_id), None)
    if not app_conf:
        return jsonify({"success": False, "message": "التطبيق مش موجود"})
    ok, msg = start_app(app_conf)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/stop/<app_id>", methods=["POST"])
def api_stop(app_id):
    ok, msg = stop_app(app_id)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/start-all", methods=["POST"])
def api_start_all():
    cfg = load_config()
    for a in cfg["apps"]:
        if a.get("enabled", True):
            start_app(a)
    return jsonify({"success": True})


@app.route("/api/stop-all", methods=["POST"])
def api_stop_all():
    cfg = load_config()
    for a in cfg["apps"]:
        stop_app(a["id"])
    return jsonify({"success": True})


if __name__ == "__main__":
    cfg = load_config()
    port = cfg.get("dashboard_port", 7500)
    print(f"\n🎛️  Ayman Termux Suite")
    print(f"🌐 http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
