print("APP STARTET")

from flask import (
    Flask, render_template, request,
    redirect, session, send_file, abort
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import sqlite3
import datetime
import io
import os
from functools import wraps

# =====================================================
# APP SETUP
# =====================================================
app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

DB_PATH = "teilnahmen.db"
PASS_PERCENT = 0.8
LOGO_CERT = "static/logo2.png"

# =====================================================
# DATABASE
# =====================================================
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS teilnahmen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                abteilung TEXT,
                datum TEXT,
                punkte INTEGER,
                gesamt INTEGER,
                bestanden INTEGER,
                zertifikat TEXT
            )
        """)

init_db()

# =====================================================
# ADMIN DECORATOR
# =====================================================
def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return wrapped

# =====================================================
# STARTSEITE
# =====================================================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        session.clear()
        session["name"] = request.form["name"]
        session["abteilung"] = request.form["department"]
        return redirect("/unterweisung/1")

    return render_template("index.html")

# =====================================================
# UNTERWEISUNGEN
# =====================================================
UNTERWEISUNGEN = [
    "01_begruesung.html",
    "02_arten.html",
    "03_grundsaetze.html",
    "04_gesetze.html",
    "05_stellen.html",
    "06_sicherheit.html",
    "07_erstehilfe.html",
    "08_brand_evakuierung.html",
    "09_unfallvermeidung.html",
    "10_abschluss.html"
]

@app.route("/unterweisung/<int:nr>")
def unterweisung(nr):
    if nr < 1 or nr > len(UNTERWEISUNGEN):
        abort(404)

    template = UNTERWEISUNGEN[nr - 1]

    if nr < len(UNTERWEISUNGEN):
        next_link = f"/unterweisung/{nr + 1}"
        next_text = "Weiter"
    else:
        next_link = "/quiz"
        next_text = "Zum Quiz"

    return render_template(
        template,
        next_link=next_link,
        next_text=next_text
    )

# =====================================================
# QUIZ
# =====================================================

QUESTIONS = [
    ("Sicherheit am Arbeitsplatz hat höchste Priorität.", True),
    ("Sicherheit behindert den Arbeitserfolg.", False),
    ("Flucht- und Rettungswege dürfen zugestellt werden.", False),
    ("Jede Verletzung muss gemeldet werden.", True),
    ("Ein Eintrag im Verbandbuch ist Pflicht.", True),
]

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    # Schutz: Quiz nur nach Start erlauben
    if "name" not in session:
        return redirect("/")

    if request.method == "POST":
        correct = 0

        # Fragen beginnen bei q1, q2, ...
        for i, (frage, richtige_antwort) in enumerate(QUESTIONS, start=1):
            user_answer = request.form.get(f"q{i}")

            # Falls eine Antwort fehlt (sollte durch required nicht passieren)
            if user_answer is None:
                continue

            # HTML liefert: "richtig" oder "falsch"
            user_bool = user_answer == "richtig"

            if user_bool == richtige_antwort:
                correct += 1

        session["punkte"] = correct
        session["gesamt"] = len(QUESTIONS)

        session["bestanden"] = int(
            correct / len(QUESTIONS) >= PASS_PERCENT
        )

        if session["bestanden"]:
            return render_template(
                "bestanden.html",
                punkte=correct,
                gesamt=len(QUESTIONS)
            )
        else:
            return render_template(
                "quiz_failed.html",
                punkte=correct,
                gesamt=len(QUESTIONS)
            )

    return render_template("quiz.html", questions=QUESTIONS)

# =====================================================
# ZERTIFIKAT
# =====================================================
@app.route("/zertifikat")
def zertifikat():
    if not session.get("bestanden"):
        return redirect("/")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    # Logo
    if os.path.exists(LOGO_CERT):
        c.drawImage(LOGO_CERT, w / 2 - 150, h - 160, 300, 150)

    # Hauptüberschrift
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(w / 2, h - 200, "Zertifikat")

    # Titel
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w / 2, h - 240, "Landal Hochwald")

    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, h - 265, "Allgemeine Sicherheitsunterweisung 2026")

    # Text
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, h - 320, "Hiermit wird bestätigt, dass")

    # Name
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, h - 355, session["name"])

    # Abteilung
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        w / 2,
        h - 385,
        f"Abteilung: {session['abteilung']}"
    )

    # Gesetzestext
    c.drawCentredString(
        w / 2,
        h - 430,
        "die Sicherheitsunterweisung gemäß § 12 Arbeitsschutzgesetz"
    )
    c.drawCentredString(
        w / 2,
        h - 455,
        "vollständig absolviert und verstanden hat."
    )

    # Datum
    datum = datetime.date.today().strftime("%d.%m.%Y")
    c.drawCentredString(w / 2, h - 510, f"Datum: {datum}")

    c.showPage()
    c.save()
    buffer.seek(0)

    # PDF speichern
    os.makedirs("zertifikate", exist_ok=True)
    filename = f"Zertifikat_{session['name'].replace(' ', '_')}_{datum}.pdf"
    path = os.path.join("zertifikate", filename)

    with open(path, "wb") as f:
        f.write(buffer.getvalue())

    # DB speichern
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            INSERT INTO teilnahmen (
                name, abteilung, datum,
                punkte, gesamt, bestanden, zertifikat
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["name"],
            session["abteilung"],
            datum,
            session["punkte"],
            session["gesamt"],
            session["bestanden"],
            path
        ))

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename
    )

# =====================================================
# ADMIN LOGIN
# =====================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None

    if request.method == "POST":
        if (
            request.form.get("username") == "admin"
            and request.form.get("password") == "admin123"
        ):
            session["admin_logged_in"] = True
            return redirect("/admin")
        else:
            error = "Falsche Zugangsdaten"

    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin/login")

# =====================================================
# ADMIN – EXCEL EXPORT
# =====================================================
@app.route("/admin/export/excel")
@admin_required
def admin_export_excel():
    import csv

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        daten = con.execute(
            "SELECT name, abteilung, datum, punkte, gesamt, bestanden FROM teilnahmen"
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    # Header
    writer.writerow([
        "Name",
        "Abteilung",
        "Datum",
        "Punkte",
        "Gesamt",
        "Bestanden"
    ])

    # Daten
    for d in daten:
        writer.writerow([
            d["name"],
            d["abteilung"],
            d["datum"],
            d["punkte"],
            d["gesamt"],
            "Ja" if d["bestanden"] else "Nein"
        ])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="Sicherheitsunterweisung_Teilnehmer.csv"
    )


# =====================================================
# ADMIN DASHBOARD
# =====================================================
@app.route("/admin")
@admin_required
def admin_dashboard():
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        daten = con.execute(
            "SELECT * FROM teilnahmen ORDER BY id DESC"
        ).fetchall()

    return render_template("admin.html", daten=daten)

# =====================================================
print("VOR RUN")
if __name__ == "__main__":
    app.run()
