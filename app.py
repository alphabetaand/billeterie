from flask import (
    Flask,
    request,
    redirect,
    url_for,
    render_template_string,
    send_file,
    session,
    send_from_directory,
)
import sqlite3
import os
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "SUPER_KEY_384758394"

ADMIN_PASSWORD = "admin123"

EVENT_CODES = {
    1: "trap team",
    2: "danslebon1",
}

DB1 = "/data/tickets.db"
DB2 = "/data/tickets_multi.db"

def init_db(path):
    if not os.path.exists(path):
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE tickets(
                number INTEGER PRIMARY KEY,
                validated_at TEXT
            )
        """
        )
        conn.commit()
        cur.executemany(
            "INSERT INTO tickets(number, validated_at) VALUES (?, NULL)",
            [(i,) for i in range(1, 301)],
        )
        conn.commit()
        conn.close()

init_db(DB1)
init_db(DB2)

BASE_HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta charset="utf-8">
<title>{{ title }}</title>

<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">

<script>
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function() {
      navigator.serviceWorker.register("/service-worker.js")
        .catch(function(err){ console.log("SW error", err); });
    });
  }

  let deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const banner = document.getElementById('install-banner');
    if (banner) banner.classList.remove('hidden');
  });

  function installApp() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(() => {
      const banner = document.getElementById('install-banner');
      if (banner) banner.classList.add('hidden');
      deferredPrompt = null;
    });
  }
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

:root{
  --bg:#020617;
  --bg2:#0b1120;
  --card:#020617;
  --primary:#fbbf24;
  --primary-soft:rgba(251,191,36,0.18);
  --danger:#ef4444;
  --success:#22c55e;
  --muted:#9ca3af;
  --border:#1f2937;
}

*{box-sizing:border-box;}

html, body {
  height: 100%;
  margin: 0;
  padding: 0;
}

body{
  margin:0;
  font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont;
  background: radial-gradient(circle at top, #1e293b 0, #020617 50%, #000 100%);
  color:#e5e7eb;
}

.wrap {
  width: 100%;
  max-width: 480px;
  margin: 0 auto;

  padding: env(safe-area-inset-top) 16px env(safe-area-inset-bottom);

  /* UTILISER TOUTE LA HAUTEUR DU TÉLÉPHONE */
  min-height: 100vh;

  display: flex;
  flex-direction: column;
  justify-content: center;

  box-sizing: border-box;
}

.card{
  background:linear-gradient(135deg, rgba(15,23,42,0.96), rgba(2,6,23,0.98));
  border-radius:18px;
  border:1px solid rgba(148,163,184,0.12);
  box-shadow:0 18px 45px rgba(0,0,0,0.7);
  padding:22px 20px 20px 20px;
  position:relative;
  overflow:hidden;
  margin: 0 auto;
  width: 100%;
  max-width: 460px;
}

.card::before{
  content:"";
  position:absolute;
  inset:-40%;
  background:radial-gradient(circle at top left, rgba(251,191,36,0.14), transparent 55%);
  opacity:0.8;
  pointer-events:none;
}

h1{
  margin:0 0 8px 0;
  font-size:22px;
}

p.lead{
  margin:0 0 14px 0;
  color:var(--muted);
  font-size:14px;
}

input{
  width:100%;
  padding:12px 13px;
  margin:8px 0 4px 0;
  border-radius:12px;
  border:1px solid var(--border);
  background:#020617;
  color:#e5e7eb;
  font-size:15px;
}

.btn{
  display:inline-block;
  border-radius:999px;
  padding:11px 16px;
  font-size:14px;
  font-weight:600;
  border:none;
  cursor:pointer;
  text-decoration:none;
}

.btn-primary{
  background:linear-gradient(135deg, #facc15, #f97316);
  color:#0b1120;
}

.btn-ghost{
  background:rgba(15,23,42,0.9);
  color:var(--muted);
  border:1px solid rgba(148,163,184,0.45);
}

.row{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  margin-top:10px;
}

.small{
  font-size:12px;
  color:var(--muted);
}

.install-banner{
  position:fixed;
  left:50%;
  bottom:16px;
  transform:translateX(-50%);
  background:rgba(15,23,42,0.96);
  border-radius:999px;
  border:1px solid rgba(148,163,184,0.4);
  padding:8px 14px;
  display:flex;
  align-items:center;
  gap:10px;
  font-size:12px;
}

.install-banner.hidden{
  display:none;
}
</style>
</head>
<body>

<div class="wrap" id="app-root">
  {{ body|safe }}
</div>

<div id="install-banner" class="install-banner hidden">
  <span>Installer l'application Billetterie ?</span>
  <button onclick="installApp()">Installer</button>
</div>

</body>
</html>
"""

def require_login():
    return session.get("logged") is True

def event_allowed(event: int) -> bool:
    return session.get(f"event_{event}_allowed") is True

def ensure_event_access(event: int) -> bool:
    if not require_login():
        return False
    if not event_allowed(event):
        return False
    return True

def db(event: int):
    return sqlite3.connect(DB1 if event == 1 else DB2)

def stats(event: int):
    conn = db(event)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tickets WHERE validated_at IS NOT NULL")
    v = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tickets")
    t = cur.fetchone()[0]
    conn.close()
    return v, t - v

def validated_list(event: int):
    conn = db(event)
    cur = conn.cursor()
    cur.execute(
        "SELECT number, validated_at FROM tickets WHERE validated_at IS NOT NULL ORDER BY validated_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory("static", "service-worker.js")

@app.route("/", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged"] = True
            return redirect(url_for("select_event"))
        else:
            error = "Mot de passe incorrect"

    body = f"""
    <div class="card">
        <h1>Connexion</h1>
        <p class="lead">Accès administrateur</p>

        <form method="post">
            <input type="password" name="password" placeholder="Mot de passe">
            <button class="btn btn-primary" type="submit">Se connecter</button>
        </form>

        {"<p style='color:#ef4444; margin-top:8px;'>" + error + "</p>" if error else ""}
    </div>
    """

    return render_template_string(BASE_HTML, title="Connexion", body=body)

@app.route("/select")
def select_event():
    if not require_login():
        return redirect(url_for("login"))

    body = """
    <div class="card" style="text-align:center;">
        <h1>Choisir un événement</h1>

        <a class="btn btn-primary" href="/event/1/code">Trap Team</a>
        <a class="btn btn-primary" href="/event/2/code">Aguiart & Co</a>

        <div style="margin-top:15px;">
            <a href="/logout" class="small">Déconnexion</a>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, title="Choix événement", body=body)

@app.route("/event/<int:event>/code", methods=["GET", "POST"])
def event_code(event):
    if not require_login():
        return redirect(url_for("login"))

    error = ""

    if request.method == "POST":
        entered = request.form.get("code", "")
        if entered == EVENT_CODES.get(event):
            session[f"event_{event}_allowed"] = True
            return redirect(f"/event/{event}")
        else:
            error = "Code incorrect"

    body = f"""
    <div class="card" style="text-align:center;">
        <h1>Code Event {event}</h1>
        <p class="lead">Entrez le code secret</p>

        <form method="post">
            <input type="password" name="code" placeholder="Code secret">
            <button class="btn btn-primary" type="submit">Valider</button>
        </form>

        {"<p style='color:#ef4444; margin-top:8px;'>" + error + "</p>" if error else ""}
    </div>
    """
    return render_template_string(BASE_HTML, title=f"Code Event {event}", body=body)
# -------------------------------------------------------
# 🏠 PAGE EVENT (Event 1 + Event 2 modifié)
# -------------------------------------------------------
@app.route("/event/<int:event>")
def event_home(event):
    if not ensure_event_access(event):
        return redirect(f"/event/{event}/code")

    v, r = stats(event)

    nav = f"""
    <div class='row' style='margin-top:18px;'>
        <a class='btn btn-ghost' href='/event{event}/validate'>Valider</a>
        <a class='btn btn-ghost' href='/event{event}/check'>Vérifier</a>
        <a class='btn btn-ghost' href='/event{event}/admin'>Admin</a>
    </div>
    <div style='margin-top:10px; text-align:center;'>
        <a href='/logout' class='small'>Déconnexion</a>
    </div>
    """

    if event == 1:
        body = f"""
        <div class="card" style="text-align:center;">
            <img src="/static/event1_logo.png"
                 style="width:75%; max-width:260px; margin:0 auto 18px auto; display:block;">
            <h1>Trap Team — XMAS TRAP #3</h1>
            <p class="lead">Tickets validés : {v} — Restants : {r}</p>
            {nav}
        </div>
        """
    else:
        body = f"""
        <div class="card" style="text-align:center;">
            <img src="/static/event2_logo.png"
                 style="width:75%; max-width:260px; margin:0 auto 18px auto; display:block;">
            <h1>DLB — DANS LE BON</h1>
            <p class="lead">Tickets validés : {v} — Restants : {r}</p>
            {nav}
        </div>
        """

    return render_template_string(BASE_HTML, title=f"Event {event}", body=body)


# -------------------------------------------------------
# 📝 VALIDATION (Event 2 → AJOUT IMAGE 55% AVANT LE TITRE)
# -------------------------------------------------------
@app.route("/event<int:event>/validate", methods=["GET", "POST"])
def validate_ticket(event):
    if not ensure_event_access(event):
        return redirect(f"/event/{event}/code")

    message = ""
    color = "#ef4444"

    if event == 2:
        header_img = "<img src='/static/event2_sleigh.png' style='width:55%; margin:0 auto 10px auto; display:block;'>"
    else:
        header_img = ""

    if request.method == "POST":
        try:
            num = int(request.form.get("number", "").strip())
            if not 1 <= num <= 300:
                raise ValueError
            conn = db(event)
            cur = conn.cursor()
            cur.execute("SELECT validated_at FROM tickets WHERE number=?", (num,))
            row = cur.fetchone()
            if row is None:
                message = f"Ticket {num} inexistant."
            elif row[0] is not None:
                message = f"Ticket {num} déjà validé ({row[0]})."
            else:
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "UPDATE tickets SET validated_at=? WHERE number=?", (now, num)
                )
                conn.commit()
                message = f"Ticket {num} validé ({now})."
                color = "#22c55e"
            conn.close()
        except Exception:
            message = "Numéro invalide (1–300)."

    v, r = stats(event)

    body = f"""
    <div class="card" style="text-align:center;">
        {header_img}
        <h1>Valider (Event {event})</h1>
        <p class="lead">Entrez un numéro entre 1 et 300.</p>

        <form method="post">
            <input type="number" name="number" min="1" max="300" placeholder="Numéro du ticket">
            <button class="btn btn-primary" type="submit">Valider</button>
        </form>

        <p class="small" style="margin-top:8px;">Validés : <b>{v}</b> — Restants : <b>{r}</b></p>
        {"<p style='margin-top:10px; color:%s; font-size:13px;'>%s</p>" % (color, message) if message else ""}

        <div class='row' style='margin-top:15px;'>
            <a class='btn btn-ghost' href='/event{event}/check'>Vérifier</a>
            <a class='btn btn-ghost' href='/event{event}/admin'>Admin</a>
        </div>
    </div>
    """

    return render_template_string(BASE_HTML, title="Valider", body=body)
# -------------------------------------------------------
# 🔍 VERIFIER (Event 2 → AJOUT IMAGE 55% AVANT LE TITRE)
# -------------------------------------------------------
@app.route("/event<int:event>/check", methods=["GET", "POST"])
def check_ticket(event):
    if not ensure_event_access(event):
        return redirect(f"/event/{event}/code")

    if event == 2:
        header_img = "<img src='/static/event2_sleigh.png' style='width:55%; margin:0 auto 10px auto; display:block;'>"
    else:
        header_img = ""

    result_html = ""

    if request.method == "POST":
        entries = request.form.get("numbers", "").replace(",", " ").split()
        conn = db(event)
        cur = conn.cursor()
        for e in entries:
            e_clean = e.strip()
            if not e_clean:
                continue
            if not e_clean.isdigit():
                result_html += f"<div class='badge-invalid'>Ticket {e_clean} invalide</div><br>"
                continue
            num = int(e_clean)
            if not 1 <= num <= 300:
                result_html += f"<div class='badge-invalid'>Ticket {num} hors plage 1–300</div><br>"
                continue
            cur.execute("SELECT validated_at FROM tickets WHERE number=?", (num,))
            row = cur.fetchone()
            if row is None:
                result_html += f"<div class='badge-invalid'>Ticket {num} inexistant</div><br>"
            elif row[0] is None:
                result_html += f"<div class='badge-not'>Ticket {num} NON validé</div><br>"
            else:
                result_html += f"<div class='badge-valid'>Ticket {num} validé ({row[0]})</div><br>"
        conn.close()

    body = f"""
    <div class="card" style="text-align:center;">
        {header_img}
        <h1>Vérifier (Event {event})</h1>
        <p class="lead">Entrez un ou plusieurs numéros (séparés par espace ou virgule).</p>

        <form method="post">
            <input type="text" name="numbers" placeholder="10 25 99">
            <button class="btn btn-primary" type="submit">Vérifier</button>
        </form>

        <div style="margin-top:14px; font-size:13px;">
            {result_html}
        </div>

        <div class='row' style='margin-top:15px;'>
            <a class='btn btn-ghost' href='/event{event}/validate'>Valider</a>
            <a class='btn btn-ghost' href='/event{event}/admin'>Admin</a>
        </div>
    </div>
    """

    return render_template_string(BASE_HTML, title="Vérifier", body=body)


# -------------------------------------------------------
# 🛠 ADMIN (Event 2 → AJOUT IMAGE 55% AVANT LE TITRE)
# -------------------------------------------------------
@app.route("/event<int:event>/admin", methods=["GET", "POST"])
def admin_event(event):
    if not ensure_event_access(event):
        return redirect(f"/event/{event}/code")

    if event == 2:
        header_img = "<img src='/static/event2_sleigh.png' style='width:55%; margin:0 auto 10px auto; display:block;'>"
    else:
        header_img = ""

    msg = ""

    if request.method == "POST":
        action = request.form.get("action", "")
        conn = db(event)
        cur = conn.cursor()

        if action == "reset_all":
            code = request.form.get("reset_code", "")
            if code != "reset":
                msg = "Code incorrect, réinitialisation impossible."
            else:
                cur.execute("UPDATE tickets SET validated_at=NULL")
                msg = "Tous les tickets ont été réinitialisés."

        elif action == "reset_one":
            try:
                num = int(request.form.get("number", "").strip())
                if 1 <= num <= 300:
                    cur.execute(
                        "UPDATE tickets SET validated_at=NULL WHERE number=?", (num,)
                    )
                    msg = f"Ticket {num} réinitialisé."
                else:
                    msg = "Numéro hors plage (1–300)."
            except Exception:
                msg = "Numéro invalide."

        conn.commit()
        conn.close()

    v, r = stats(event)

    body = f"""
    <div class="card" style="text-align:center;">
        {header_img}
        <h1>Admin Event {event}</h1>
        <p class="lead">Validés : <b>{v}</b> — Restants : <b>{r}</b></p>

        <a class="btn btn-success" href="/event{event}/export/pdf">Exporter PDF des tickets validés</a>

        <hr>

        <form method="post" style="margin-top:12px;">
            <input type="password" name="reset_code" placeholder="Code de réinitialisation (reset)" required>
            <button class="btn btn-danger" name="action" value="reset_all" type="submit">
                Réinitialiser tout l'événement
            </button>
        </form>

        <form method="post" style="margin-top:12px;">
            <input type="number" name="number" placeholder="Ticket à réinitialiser (1–300)">
            <button class="btn btn-ghost" name="action" value="reset_one" type="submit">
                Réinitialiser un ticket
            </button>
        </form>

        {f"<p style='margin-top:10px; color:#22c55e; font-size:13px;'>{msg}</p>" if msg else ""}

        <div class='row' style='margin-top:15px;'>
            <a class='btn btn-ghost' href='/event{event}/validate'>Valider</a>
            <a class='btn btn-ghost' href='/event{event}/check'>Vérifier</a>
            <a href='/logout-protect' class='small' style='color:#f87171;'>Déconnexion</a>
        </div>
    </div>
    """

    return render_template_string(BASE_HTML, title="Admin", body=body)

# -------------------------------------------------------
# 🖨 EXPORT PDF
# -------------------------------------------------------
@app.route("/event<int:event>/export/pdf")
def export_pdf(event):
    if not ensure_event_access(event):
        return redirect(f"/event/{event}/code")

    rows = validated_list(event)
    buff = io.BytesIO()

    pdf = canvas.Canvas(buff)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 800, f"Event {event} - Tickets validés")
    pdf.setFont("Helvetica", 12)

    y = 770
    for n, d in rows:
        pdf.drawString(50, y, f"Ticket {n} - {d}")
        y -= 20
        if y < 50:
            pdf.showPage()
            y = 800

    pdf.save()
    buff.seek(0)

    # 🔥 SAFARI + PWA : on enregistre le PDF dans /data
    filename = f"event{event}_validated.pdf"
    filepath = f"/data/{filename}"

    with open(filepath, "wb") as f:
        f.write(buff.getbuffer())

    # 🔥 On redirige vers une URL que iPhone peut ouvrir
    return redirect(f"/download/{filename}")


# -------------------------------------------------------
# 🚪 LOGOUT SIMPLE
# -------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


LOGOUT_CODE = "exit"


# -------------------------------------------------------
# 🔐 LOGOUT PROTÉGÉ PAR CODE
# -------------------------------------------------------
@app.route("/logout-protect", methods=["GET", "POST"])
def logout_protect():
    if not require_login():
        return redirect("/")

    error = ""

    if request.method == "POST":
        code = request.form.get("code", "")
        if code == LOGOUT_CODE:
            session.clear()
            return redirect("/")
        else:
            error = "Code incorrect"

    body = f"""
    <div class='card'>
        <h1>Code de déconnexion</h1>
        <p class='lead'>Entrez le code pour vous déconnecter.</p>

        <form method='post'>
            <input type='password' name='code' placeholder='Code secret'>
            <button class='btn btn-danger'>Déconnexion</button>
        </form>

        {f"<p style='color:#dc2626; margin-top:10px;'>{error}</p>" if error else ""}
    </div>
    """

    return render_template_string(BASE_HTML, title="Déconnexion sécurisée", body=body)

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("/data", filename)

# -------------------------------------------------------
# ▶ RUN (local seulement)
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
