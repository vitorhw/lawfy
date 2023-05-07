import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps

# ERROR MESSAGE FOR OCASIONS


def apology(message, code=400):
    return render_template("apology.html", message=message, code=code)

# REQUIRES LOGIN FOR INNER PAGES


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") != 3:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# GET RANDOM PASSWORD FOR CLIENTS


def get_pass():

    # CONTACT API
    response = requests.get(
        "https://api.happi.dev/v1/generate-password?apikey=")

    # PARSING RESPONSE
    answer = response.json()
    return {
        "password": answer["passwords"]
    }
