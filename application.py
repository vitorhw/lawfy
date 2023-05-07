import os
import datetime

from datetime import datetime
from cs50 import SQL
from databases import Database
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import *

# SETTING UP APPLICATION
app = Flask(__name__)

# RELOADING TEMPLATES AUTOMATICALLY
app.config["TEMPLATES_AUTO_RELOAD"] = True

# DISABLING CACHE
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# USING FILESYSTEM INSTEAD OF COOKIES
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# CONFIGURING THE DATABASE
db = SQL('sqlite:///database.db')

# LOGIN PAGE SHOWS PROCESSES USERS HAVE IN THEIR NAME
@app.route("/")
@login_required
def index():

    if session["user_id"] == 3:
        return redirect("/admin")

    name = db.execute("SELECT name FROM users WHERE id = :user_id", user_id = session["user_id"])

    cases = db.execute("SELECT * FROM cases WHERE user_id = :user_id ORDER BY ID DESC", user_id = session["user_id"])

    for case in cases:
        lawyer = db.execute("SELECT name FROM users WHERE id = (SELECT owner_id FROM cases WHERE id = :case_id)", case_id = case['id'])
        case['lawyer'] = lawyer[0]['name']

        updates = db.execute("SELECT action FROM updates WHERE case_id = :doc_id ORDER BY id DESC", doc_id=case['id'])
        if updates:
            case['action'] = updates[0]['action']
        else:
            case['action'] = 'no'

    return render_template("index.html", cases=cases, name=name)

# LOGIN PAGE
@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("Missing CPF", 403)

        elif not request.form.get("password"):
            return apology("Missing password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username = request.form.get("username"))

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("Invalid CPF and/or password", 403)

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    else:
        return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
@login_required
@admin_login_required
def register():

    if request.method == "POST":

        pw = get_pass()['password'][0]

        if not request.form.get("username") or not request.form.get("name"):
            return apology("Missing field", 403)

        matches = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        if matches:
            return apology("CPF already registered", 403)

        db.execute("INSERT INTO users (username, hash, name) VALUES (:username, :hashed, :name)",
                    username=request.form.get("username"), hashed=generate_password_hash(pw), name=request.form.get("name"))


        cpf = request.form.get("username")
        name = request.form.get("name")

        return render_template("register_success.html", cpf=cpf, pw=pw, name=name)

    else:

        return render_template("register.html")

@app.route("/caseinfo")
@login_required
def caseinfo():

    doc_id = request.args.get("id")

    if not doc_id:
        return apology("Page not found", 404)

    ownership = db.execute("SELECT user_id, owner_id FROM cases WHERE id = :doc_id", doc_id=doc_id)

    if not ownership:
        return apology("Page not found", 404)

    if ownership[0]['user_id'] != session["user_id"]:
        return apology("Permission denied", 403)

    data = db.execute("SELECT * FROM cases where id = :doc_id", doc_id=doc_id)
    updates = db.execute("SELECT * FROM updates WHERE case_id = :doc_id ORDER BY id DESC", doc_id=doc_id)

    lawyer = db.execute("SELECT name FROM users WHERE id = (SELECT owner_id FROM cases WHERE id = :case_id)", case_id = doc_id)

    return render_template("caseinfo.html", data=data, updates=updates, lawyer=lawyer)

@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_login_required
def admin():

    return render_template("admin.html")


@app.route("/search", methods=["GET", "POST"])
@login_required
@admin_login_required
def search():

    if request.method == "POST":

        query = request.form.get("query")

        results = db.execute('SELECT * FROM users WHERE name = :name OR username = :cpf', name = query, cpf = query)

        return render_template("search.html", results=results)

    return redirect("/")

@app.route("/profile")
@login_required
@admin_login_required
def profile():

    user_id = request.args.get("id")

    if not user_id:
        return redirect("/admin")

    data = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=user_id)

    cases = db.execute("SELECT * FROM cases WHERE user_id = :user_id", user_id=user_id)

    return render_template("profile.html", data=data, cases=cases)

@app.route("/update", methods=["GET", "POST"])
@login_required
@admin_login_required
def update():

    if request.method == "POST":

        username = request.form.get("old_username")

        new_username = request.form.get("username")
        new_name = request.form.get("name")

        db.execute("UPDATE users SET username=:new_username, name=:new_name WHERE username=:username", new_username=new_username, new_name=new_name, username=username)

        flash("User updated!")
        return redirect("/admin")


    return redirect("/")

@app.route("/reset_pass", methods=["GET", "POST"])
@login_required
@admin_login_required
def reset_pass():

    if request.method == "POST":

        user_id = request.form.get("id")
        cpf = request.form.get("username")
        name = request.form.get("name")

        pw = get_pass()['password'][0]

        db.execute("UPDATE users SET hash=:hashed WHERE id=:user_id", hashed=generate_password_hash(pw), user_id=user_id)

        return render_template("register_success.html", cpf=cpf, pw=pw, name=name)

    return redirect("/")

@app.route("/push", methods=["GET", "POST"])
@login_required
@admin_login_required
def push():

    if request.method == "POST":

        content = request.form.get("content")
        action = request.form.get("action")
        case_id = request.form.get("case_id")
        progress = request.form.get("progress")
        time = datetime.now()

        db.execute("INSERT INTO updates (content, case_id, time, action) VALUES (:content, :case_id, :time, :action)", content=content, case_id=case_id, time=time, action=action)

        db.execute("UPDATE cases SET progress = :progress, 'update' = :time WHERE id = :case_id", progress=progress, time=time, case_id=case_id)

        flash("Sent!")

    return redirect("/")

@app.route("/create_case", methods=["GET", "POST"])
@login_required
@admin_login_required
def create_case():

    if request.method == "POST":

        username = request.form.get("username")
        name = request.form.get("name")
        area = request.form.get("area")
        content = request.form.get("content")
        time = datetime.now()

        user_id = db.execute("SELECT id FROM users WHERE username = :username", username=username)
        user_id = user_id[0]['id']

        owner_id = session["user_id"]

        result = db.execute("INSERT INTO cases (user_id, owner_id, name, area, 'update', progress) VALUES (:user_id, :owner_id, :name, :area, :update, :progress)", user_id=user_id, owner_id=owner_id, name=name, area=area, update=time, progress=0)

        db.execute("INSERT INTO updates (content, case_id, time, action) VALUES (:content, :case_id, :time, :action)", content=content, case_id=result, time=time, action="no")

        flash("Created!")
        return redirect("/")

    return redirect("/")


# HANDLE ERRORS
def errorhandler(e):
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# RETRIEVE ERRORS
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
