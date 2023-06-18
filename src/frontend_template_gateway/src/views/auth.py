from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session, abort
import requests
import jwt
from datetime import datetime, timedelta
from functools import wraps


auth = Blueprint('auth', __name__, template_folder='templates')
auth.config = {}
auth.config["SECRET_KEY"] = "secretkey"


@auth.route('/login')
def login():
    if session.get('Authorization'):
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), auth.config["SECRET_KEY"], algorithms=["HS256"])
            user_role = decoded_token.get('role')

            # check the role!!!
            if user_role == "consumer":
                return redirect(url_for('auth.main_page'))  # change to main page
            else:
                return redirect(url_for('auth.main_page'))  # change to main page

        except jwt.ExpiredSignatureError:
            return render_template('login.html')
    return render_template('login.html')


@auth.route('/login', methods=['POST'])
def login_post():
    password = request.form.get('password')
    email = request.form.get('email')

    if not password:
        flash('Password is required!', 'error')
    elif not email:
        flash('Email is required!', 'error')
    else:
        auth_data = ({
            'password': password,
            'email': email
        })

        auth_url = 'http://host.docker.internal:8004/login'
        response = requests.post(auth_url, json=auth_data)

        if response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
        elif response.status_code == 200:
            data_response = response.json()
            token = data_response["access_token"]

            try:
            # Verify the token
                decoded_token = jwt.decode(token, auth.config["SECRET_KEY"], algorithms=["HS256"])
                user_role = decoded_token.get('role')
                user_id = decoded_token.get('sub')
                user_name = decoded_token.get('username')

                session['Authorization'] = token
                session['user_role'] = user_role
                session['user_id'] = user_id
                session['user_name'] = user_name


                return redirect(url_for('auth.main_page'))  # change to main page

            except jwt.ExpiredSignatureError:
                return render_template('login.html')

            
            # flash(data_response["message"], 'success')
            # return redirect(url_for('auth.main_page'))  # change to main page
        else:
            flash("Error has occurred", 'error')

    return render_template('login.html')


@auth.route('/signup')
def signup():
    print(request.referrer)
    return render_template('signup.html')


@auth.route('/signup', methods=['POST'])
def signup_post():
    print("hello")

    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    role = request.form.get('role')

    if not username:
        flash('Username is required!', 'error')
    elif not password:
        flash('Password is required!', 'error')
    elif not email:
        flash('Email is required!', 'error')
    else:

        auth_data = ({
            'username': username,
            'password': password,
            'email': email,
            'role': role
        })

        auth_url = 'http://host.docker.internal:8004/signup'
        response = requests.post(auth_url, json=auth_data)

        if response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
        elif response.status_code == 201:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect('/login')
        else:
            flash("Error has occurred", 'error')

    return render_template('signup.html')


@auth.route('/logout')
def logout():
    if session.get("Authorization"):
        session.pop('Authorization', None)
        session.pop('user_role', None)
        session.pop('user_id', None)
        session.pop('user_name', None)

    return redirect(url_for('auth.login'))


@auth.route('/main')
def main_page():
    if session.get('Authorization'):
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), auth.config["SECRET_KEY"], algorithms=["HS256"])
            user_role = decoded_token.get('role')

            # check the role!!!
            if user_role == "consumer":
                return render_template('welcome_consumer.html')  # change to main page
            else:
                return render_template('welcome_producer.html')  # change to main page

        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))
    else:
        abort(404)

