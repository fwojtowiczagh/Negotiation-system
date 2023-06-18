from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session, abort, Response
import requests
import jwt
from datetime import datetime, timedelta
from functools import wraps
import re
import pika
import time
from flask_cors import CORS
from flask_sse import sse


producer = Blueprint('producer', __name__, template_folder='templates')
producer.config = {}
producer.config["SECRET_KEY"] = "secretkey"


@producer.route('/create')
def create_product():
    print(session.get('Authorization'))
    if session.get('Authorization') and session.get('user_role') == 'producer':
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), producer.config["SECRET_KEY"], algorithms=["HS256"])

            # check the role!!!
            return render_template('create_product.html')

        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))
    else:
        abort(401)


@producer.route('/create', methods=['POST'])
def create_product_post():
    name = request.form.get('name')
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    print(type(quantity))
    producer_id = session.get('user_id')

    if not name:
        flash('Name is required!', 'error')
    elif not price:
        flash('Price is required!', 'error')
    elif not quantity:
        flash('Quantity is required!', 'error')
    else:
        data = ({
            'name': name,
            'price': int(price),
            'quantity': int(quantity),
        })

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8001/{producer_id}/products'
        response = requests.post(auth_url, json=data, headers=headers)

        if response.status_code == 201:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect('/main')
        elif response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/create')
        elif response.status_code == 401:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/logout')
        elif response.status_code == 403:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/main')
        else:
            flash("Error has occurred", 'error')

    return render_template('create_product.html')


@producer.route('/products')
def show_products():
    print(session.get('Authorization'))
    if session.get('Authorization') and session.get('user_role') == 'producer':
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), producer.config["SECRET_KEY"], algorithms=["HS256"])
            producer_id = session.get('user_id')

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8001/{producer_id}/products'
            response = requests.get(auth_url, headers=headers)

            if response.status_code == 200:
                data_response = response.json()
                return render_template('show_products_producer.html', products=data_response)
            elif response.status_code == 401:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/logout')
            elif response.status_code == 403 or response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/main')
            else:
                flash("Error has occurred", 'error')

            # check the role!!!
            return redirect('/main')

        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))
    else:
        abort(401)


@producer.route('/products', methods=['POST'])
def delete_product():
    if re.match(r"delete_\d", request.form['submit']):
        number = request.form['submit'][len("delete_"):]
        producer_id = request.form.get(f'producer_id_{number}')
        product_id = request.form.get(f'product_id_{number}')

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8001/{producer_id}/products/{product_id}'
        response = requests.delete(auth_url, headers=headers)

        if response.status_code == 200:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect('/products')
        elif response.status_code == 401:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/logout')
        elif response.status_code == 403 or response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/products')
        else:
            flash("Error has occurred", 'error')
            return redirect('/products')
    else:
        flash("Invalid action", 'error')
        return redirect('/products')


@producer.route('/edit/<int:product_id>')
def edit_product(product_id):
    print(session.get('Authorization'))
    if session.get('Authorization') and session.get('user_role') == 'producer':
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), producer.config["SECRET_KEY"], algorithms=["HS256"])

            # check the role!!!
            return render_template('edit_product.html', product_id=product_id)

        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))
    else:
        abort(401)


@producer.route('/edit/<int:product_id>', methods=['POST'])
def edit_product_post(product_id):
    name = request.form.get('name')
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    producer_id = session.get('user_id')

    data = {}

    if name:
        data['name'] = name
    if price:
        data['price'] = price
    if quantity:
        data['quantity'] = quantity

    if data:
        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8001/{producer_id}/products/{product_id}'
        response = requests.put(auth_url, json=data, headers=headers)

        if response.status_code == 200:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect('/products')
        elif response.status_code == 401:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/logout')
        elif response.status_code == 403 or response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return render_template('edit_product.html', product_id=product_id)
        else:
            flash("Error has occurred", 'error')
    else:
        flash("No data registered!", 'error')

    return render_template('edit_product.html', product_id=product_id)


@producer.route('/offers')
def show_offers():
    print(session.get('Authorization'))
    if session.get('Authorization') and session.get('user_role') == 'producer':
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), producer.config["SECRET_KEY"], algorithms=["HS256"])
            producer_id = session.get('user_id')

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8003/producers/{producer_id}/offers'
            response = requests.get(auth_url, headers=headers)

            if response.status_code == 200:
                data_response = response.json()
                if session.get('isButtonDisabled'):
                    isButtonDisabled = session.get('isButtonDisabled')
                    print(isButtonDisabled)
                    session.pop('isButtonDisabled', None)
                    return render_template('offers_producer.html', products=data_response, isButtonDisabled=isButtonDisabled)
                return render_template('offers_producer.html', products=data_response)
            elif response.status_code == 401:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/logout')
            elif response.status_code == 403 or response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/main')
            else:
                flash("Error has occurred", 'error')

            # check the role!!!
            return redirect('/main')

        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))
    else:
        abort(401)


@producer.route('/offers', methods=['POST'])
def counteroffer_post():
    if re.match(r"delete_\d", request.form['submit']):
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), producer.config["SECRET_KEY"], algorithms=["HS256"])
            number = request.form['submit'][len("delete_"):]
            offer_id = request.form.get(f'id_{number}')

            auth_url = f'http://host.docker.internal:8003/delete/{offer_id}'
            response = requests.delete(auth_url)

            if response.status_code == 200:
                data_response = response.json()
                flash(data_response["message"], 'success')
                return redirect('/offers')
            elif response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/offers')
            else:
                flash("Error has occurred, try again later!", 'error')
                return redirect('/offers')
        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))

    elif re.match(r"counter_\d", request.form['submit']):
        number = request.form['submit'][len("counter_"):]
        price = request.form.get(f'price_post_{number}')
        producer_id = session.get('user_id')
        user_id = request.form.get(f'user_id_{number}')
        offer_id = request.form.get(f'id_{number}')
        print(price)
        print(offer_id)

        if not price:
            flash('Set the price!', 'error')
            return redirect('/offers')
        else:
            data = {
                "user_id": user_id,
                "producer_id": producer_id,
                "price": int(price),
                "offer_id": offer_id
            }

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8001/{producer_id}/offers/{offer_id}/counteroffer'
            response = requests.post(auth_url, json=data, headers=headers)

        #     if response.status_code == 201:
        #         data_response = response.json()
        #         flash(data_response["message"], 'success')
        #         session['isButtonDisabled'] = True
        #         return redirect('/offers')
        #     elif response.status_code == 401:
        #         data_response = response.json()
        #         flash(data_response["message"], 'error')
        #         return redirect('/logout')
        #     elif response.status_code == 403:
        #         data_response = response.json()
        #         flash(data_response["message"], 'error')
        #         return redirect('/offers')
        #     else:
        #         flash("Error has occurred, try again later!", 'error')

        # return redirect('/offers')

    elif re.match(r"accepted_\d", request.form['submit']):
        number = request.form['submit'][len("accepted_"):]
        producer_id = session.get('user_id')
        user_id = request.form.get(f'user_id_{number}')
        offer_id = request.form.get(f'id_{number}')

        data = {
                "user_id": user_id,
                "producer_id": producer_id,
                "offer_id": offer_id
            }

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8001/{producer_id}/offers/{offer_id}/accept'
        response = requests.post(auth_url, json=data, headers=headers)

    elif re.match(r"declined_\d", request.form['submit']):
        number = request.form['submit'][len("declined_"):]
        producer_id = session.get('user_id')
        user_id = request.form.get(f'user_id_{number}')
        offer_id = request.form.get(f'id_{number}')

        data = {
                "user_id": user_id,
                "producer_id": producer_id,
                "offer_id": offer_id
            }

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8001/{producer_id}/offers/{offer_id}/decline'
        response = requests.post(auth_url, json=data, headers=headers)

    if response.status_code == 201:
        data_response = response.json()
        flash(data_response["message"], 'success')
        session['isButtonDisabled'] = [f"producer{number}", number]
        return redirect('/offers')
    elif response.status_code == 401:
        data_response = response.json()
        flash(data_response["message"], 'error')
        return redirect('/logout')
    elif response.status_code == 403:
        data_response = response.json()
        flash(data_response["message"], 'error')
        return redirect('/offers')
    else:
        flash("Error has occurred, try again later!", 'error')
        return redirect('/offers')

