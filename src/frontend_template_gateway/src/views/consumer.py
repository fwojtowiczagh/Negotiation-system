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


consumer = Blueprint('consumer', __name__, template_folder='templates')
consumer.config = {}
consumer.config["SECRET_KEY"] = "secretkey"


@consumer.route('/producers')
def producers():
    if session.get('Authorization'):
        auth_url = 'http://host.docker.internal:8004/producers'
        response = requests.get(auth_url)

        if response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
        elif response.status_code == 200:
            data_response = response.json()
            return render_template('producers.html', producers=data_response)
        else:
            flash("Error has occurred", 'error')

    # previous_page = request.referrer[len(request.host_url)-1:] if request.referrer else '/main'
    # return redirect(previous_page)
    else:
        abort(401)


@consumer.route('/products/<int:producer_id>')
def show_products(producer_id):
    print(session.get('Authorization'))
    if session.get('Authorization') and session.get('user_role') == 'consumer':
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), consumer.config["SECRET_KEY"], algorithms=["HS256"])
            # consumer_id = session.get('user_id')

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8001/{producer_id}/products'
            response = requests.get(auth_url, headers=headers)

            if response.status_code == 200:
                data_response = response.json()
                return render_template('show_products_consumer.html', products=data_response, producer_id=producer_id)
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


@consumer.route('/products/<int:producer_id>', methods=['POST'])
def show_products_post(producer_id):
    print(session.get('Authorization'))
    if re.match(r"cart_\d", request.form['submit']):
        number = request.form['submit'][len("cart_"):]
        consumer_id = session.get('user_id')
        product_name = request.form.get(f"name_{number}")
        price = request.form.get(f"price_{number}")
        product_id = request.form.get(f"product_id_{number}")
        quantity = request.form.get(f"quantity_{number}")

        if not quantity:
            flash('Set the price!', 'error')
            return redirect(url_for('consumer.show_products', producer_id=producer_id))
        else:
            data = {
                "product_name": product_name,
                "quantity": int(quantity),
                "price": int(price)
            }

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8002/{consumer_id}/{producer_id}/products/{product_id}'
            response = requests.post(auth_url, json=data, headers=headers)

            if response.status_code == 201:
                data_response = response.json()
                flash(data_response["message"], 'success')
                return redirect(url_for('consumer.show_products', producer_id=producer_id))
            elif response.status_code == 401:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/logout')
            elif response.status_code == 403 or response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect(url_for('consumer.show_products', producer_id=producer_id))
            else:
                flash("Error has occurred", 'error')
                return redirect(url_for('consumer.show_products', producer_id=producer_id))

    elif re.match(r"offer_\d", request.form['submit']):
        number = request.form['submit'][len("offer_"):]
        consumer_id = session.get('user_id')
        product_name = request.form.get(f"name_{number}")
        price = request.form.get(f"newprice_{number}")
        product_id = request.form.get(f"product_id_{number}")

        if not price:
            flash('Set the price!', 'error')
            return redirect(url_for('consumer.show_products', producer_id=producer_id))
        else:
            data = {
                "product_name": product_name,
                "price": int(price)
            }

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8002/{consumer_id}/{producer_id}/products/{product_id}/offer'
            response = requests.post(auth_url, json=data, headers=headers)

            if response.status_code == 201:
                data_response = response.json()
                flash(data_response["message"], 'success')
                return redirect(url_for('consumer.show_products', producer_id=producer_id))
            elif response.status_code == 401:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/logout')
            elif response.status_code == 403 or response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect(url_for('consumer.show_products', producer_id=producer_id))
            else:
                flash("Error has occurred", 'error')
                return redirect(url_for('consumer.show_products', producer_id=producer_id))
                
    return redirect(url_for('consumer.show_products', producer_id=producer_id))


@consumer.route('/offers')
def show_offers():
    print(session.get('Authorization'))
    if session.get('Authorization') and session.get('user_role') == 'consumer':
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), consumer.config["SECRET_KEY"], algorithms=["HS256"])
            consumer_id = session.get('user_id')

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8003/consumers/{consumer_id}/offers'
            response = requests.get(auth_url, headers=headers)

            if response.status_code == 200:
                data_response = response.json()
                if session.get('isButtonDisabled'):
                    isButtonDisabled = session.get('isButtonDisabled')
                    print(isButtonDisabled)
                    session.pop('isButtonDisabled', None)
                    return render_template('offers_consumer.html', products=data_response, isButtonDisabled=isButtonDisabled)
                return render_template('offers_consumer.html', products=data_response)
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


@consumer.route('/offers', methods=['POST'])
def show_offers_post():
    if re.match(r"delete_\d", request.form['submit']):
        try:
            # Verify the token
            decoded_token = jwt.decode(session.get('Authorization'), consumer.config["SECRET_KEY"], algorithms=["HS256"])
            number = request.form['submit'][len("delete_"):]
            offer_id = request.form.get(f'id_{number}')

            auth_url = f'http://host.docker.internal:8003/delete/{offer_id}'
            response = requests.delete(auth_url)

            if response.status_code == 200:
                data_response = response.json()
                flash(data_response["message"], 'success')
                return redirect('/consumer/offers')
            elif response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/consumer/offers')
            else:
                flash("Error has occurred, try again later!", 'error')
                return redirect('/consumer/offers')
        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))

    elif re.match(r"accepted_\d", request.form['submit']):
        number = request.form['submit'][len("accepted_"):]
        user_id = session.get('user_id')
        producer_id = request.form.get(f'producer_id_{number}')
        offer_id = request.form.get(f'id_{number}')
        product_name = request.form.get(f'product_name_{number}')
        product_id = request.form.get(f'product_id_{number}')
        price = request.form.get(f'price_{number}')
        quantity = request.form.get(f'quantity_{number}')

        if not quantity:
            flash('Set the correct amount!', 'error')
            return redirect('/consumer/offers')
        else:

            data = {
                    "user_id": user_id,
                    "producer_id": producer_id,
                    "offer_id": offer_id,
                    "product_name": product_name,
                    "product_id": product_id,
                    "price": price,
                    "quantity": int(quantity)
                }

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8002/{user_id}/offers/{product_id}/accept'
            response = requests.post(auth_url, json=data, headers=headers)

    elif re.match(r"declined_\d", request.form['submit']):
        number = request.form['submit'][len("declined_"):]
        user_id = session.get('user_id')
        producer_id = request.form.get(f'producer_id_{number}')
        offer_id = request.form.get(f'id_{number}')
        product_id = request.form.get(f'product_id_{number}')

        data = {
                "user_id": user_id,
                "producer_id": producer_id,
                "offer_id": offer_id
            }

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8002/{user_id}/offers/{product_id}/decline'
        response = requests.post(auth_url, json=data, headers=headers)

    if response.status_code == 201:
        data_response = response.json()
        flash(data_response["message"], 'success')
        session['isButtonDisabled'] = [f"consumer{number}", number]
        return redirect('/consumer/offers')
    elif response.status_code == 401:
        data_response = response.json()
        flash(data_response["message"], 'error')
        return redirect('/logout')
    elif response.status_code == 403:
        data_response = response.json()
        flash(data_response["message"], 'error')
        return redirect('/consumer/offers')
    else:
        flash("Error has occurred, try again later!", 'error')
        return redirect('/consumer/offers')


@consumer.route('/cart')
def show_cart():
    if session.get('Authorization') and session.get('user_role') == 'consumer':
        try:
            decoded_token = jwt.decode(session.get('Authorization'), consumer.config["SECRET_KEY"], algorithms=["HS256"])
            consumer_id = session.get('user_id')

            token = session.get('Authorization')
            headers = {'Authorization': token}

            auth_url = f'http://host.docker.internal:8002/{consumer_id}/cart'
            response = requests.get(auth_url, headers=headers)

            if response.status_code == 403 or response.status_code == 400:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/main')
            elif response.status_code == 200:
                data_response = response.json()
                return render_template('cart.html', items=data_response)
            elif response.status_code == 401:
                data_response = response.json()
                flash(data_response["message"], 'error')
                return redirect('/logout')
            else:
                flash("Error has occurred", 'error')

        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))

    # previous_page = request.referrer[len(request.host_url)-1:] if request.referrer else '/main'
    # return redirect(previous_page)
    else:
        abort(401)


@consumer.route('/cart', methods=['POST'])
def show_cart_post():
    print(session.get('Authorization'))
    if re.match(r"delete_\d", request.form['submit']):
        number = request.form['submit'][len("delete_"):]
        consumer_id = session.get('user_id')
        item_id = request.form.get(f"item_id_{number}")

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8002/{consumer_id}/cart/{item_id}/delete'
        response = requests.delete(auth_url, headers=headers)

        if response.status_code == 200:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect(url_for('consumer.show_cart'))
        elif response.status_code == 401:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/logout')
        elif response.status_code == 403 or response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect(url_for('consumer.show_cart'))
        else:
            flash("Error has occurred", 'error')
            return redirect(url_for('consumer.show_cart'))

    elif re.match(r"add_quantity_\d", request.form['submit']):
        number = request.form['submit'][len("add_quantity_"):]
        consumer_id = session.get('user_id')
        item_id = request.form.get(f"item_id_{number}")
        quantity = request.form.get(f"add_quantity_{number}")

        data = {
                "quantity": int(quantity)
            }

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8002/{consumer_id}/cart/{item_id}/update'
        response = requests.put(auth_url, json=data, headers=headers)

        if response.status_code == 200:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect(url_for('consumer.show_cart'))
        elif response.status_code == 401:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/logout')
        elif response.status_code == 403 or response.status_code == 400:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect(url_for('consumer.show_cart'))
        else:
            flash("Error has occurred", 'error')
            return redirect(url_for('consumer.show_cart'))

    elif request.form['submit'] == "purchase":
        consumer_id = session.get('user_id')

        token = session.get('Authorization')
        headers = {'Authorization': token}

        auth_url = f'http://host.docker.internal:8002/{consumer_id}/cart/purchase'
        response = requests.get(auth_url, headers=headers)

        if response.status_code == 200:
            data_response = response.json()
            flash(data_response["message"], 'success')
            return redirect(url_for('consumer.show_cart'))
        elif response.status_code == 401:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect('/logout')
        elif response.status_code == 403 or response.status_code == 400 or response.status_code == 500:
            data_response = response.json()
            flash(data_response["message"], 'error')
            return redirect(url_for('consumer.show_cart'))
        else:
            flash("Error has occurred", 'error')
            return redirect(url_for('consumer.show_cart'))

    return redirect(url_for('consumer.show_cart'))
