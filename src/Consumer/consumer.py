from dataclasses import dataclass
from flask import Flask, jsonify, abort, request, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_cors import CORS
from flask_sse import sse  # add in req.txt
# from flask_script import Manager
import requests
import jwt
from datetime import datetime, timedelta
from functools import wraps
import pika
import json


app = Flask(__name__)
app.register_blueprint(sse, url_prefix='/stream')
app.config["SECRET_KEY"] = "secretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = 'mysql://root:root@db_consumer/consumer'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            # token = request.headers.get('Authorization', '').replace('Bearer ', '')  # another option?

            # check if the authorization header exists
            if 'Authorization' in request.headers:
                token = request.headers['Authorization']

            # return error if no token provided
            if not token:
                return jsonify({'message': 'Token is missing!'}), 401

            try:
                decoded_token = jwt.decode(token, app.config["SECRET_KEY"], algorithms=['HS256'])
                user_role = decoded_token.get('role')
                user_id = decoded_token.get('sub')
                
                if role == "allaccess":
                    return f(*args, **kwargs)
                elif user_role == role and ('user_id' not in kwargs or user_id == kwargs.get('user_id')):
                    return f(*args, **kwargs)
                else:
                    return jsonify({'message': 'Insufficient privileges'}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Token has expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'message': 'Invalid token'}), 401

        return decorated_function
    return decorator


def get_user_id():
    token = request.headers['Authorization']




@dataclass
class Purchase(db.Model):
    id: int
    product_id: int
    producer_id: int
    user_id: int
    product_name: str
    price: int
    quantity: int
    is_purchased: bool

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False)
    producer_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    is_purchased = db.Column(db.Boolean, default=False)


@app.route('/')
def read_cosnumers():
    return "hello"


@app.route('/<int:user_id>/<int:producer_id>/products/<int:product_id>', methods=['POST'])
@role_required('consumer')
def add_to_shopping_cart(user_id, producer_id, product_id):
    product_name = request.json.get("product_name")
    price = request.json.get("price")
    quantity = request.json.get("quantity")

    in_cart = Purchase.query.filter_by(user_id=user_id, product_name=product_name, product_id=product_id, producer_id=producer_id, is_purchased=False).first()
    if in_cart:
        in_cart.quantity += quantity
        in_cart.price = price
    else:
        product = Purchase(product_name=product_name, price=price, quantity=quantity, product_id=product_id, producer_id=producer_id, user_id=user_id, is_purchased=False)
        db.session.add(product)
    db.session.commit()
    return jsonify({'message': 'Product successfully added to the cart.'}), 201


@app.route('/<int:user_id>/cart/<int:product_id>')
@role_required('consumer')
def get_item_from_cart(user_id, product_id):
    product = Purchase.query.filter_by(user_id=user_id, product_id=product_id, is_purchased=False).first()
    if not product:
        return jsonify({'message': 'No such product in the cart'}), 400
    return jsonify(product)


@app.route('/<int:user_id>/all')
@role_required('consumer')
def get_all_from_cart(user_id):
    products = Purchase.query.filter_by(user_id=user_id).all()
    if not products:
        return jsonify({'message': 'Cart is empty'}), 400
    return jsonify(products), 200


@app.route('/<int:user_id>/cart')
@role_required('consumer')
def get_items_from_cart(user_id):
    products = Purchase.query.filter_by(user_id=user_id, is_purchased=False).all()
    if not products:
        return jsonify({'message': 'Cart is empty'}), 400
    return jsonify(products)


@app.route('/<int:user_id>/purchased')
@role_required('consumer')
def get_purchased_items(user_id):
    products = Purchase.query.filter_by(user_id=user_id, is_purchased=True).all()
    if not products:
        return jsonify({'message': 'Cart is empty'}), 400
    return jsonify(products), 200


@app.route('/<int:user_id>/cart/<int:cart_id>/delete', methods=['DELETE'])
@role_required('consumer')
def delete_item_from_cart(user_id, cart_id):
    product = Purchase.query.filter_by(user_id=user_id, id=cart_id, is_purchased=False).first()
    if not product:
        return jsonify({'message': 'No such product in the cart'}), 400
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product successfully deleted from cart.'}), 200


@app.route('/<int:user_id>/cart/<int:cart_id>/update', methods=['PUT'])
@role_required('consumer')
def change_quantity_of_product(user_id, cart_id):
    quantity = request.json.get("quantity")

    product = Purchase.query.filter_by(user_id=user_id, id=cart_id, is_purchased=False).first()
    if not product:
        return jsonify({'message': 'No such product in the cart'}), 400

    product.quantity += quantity
    if product.quantity <= 0:
        db.session.delete(product)

    db.session.commit()
    return jsonify({'message': 'Product successfully updated.'}), 200


@app.route('/<int:user_id>/cart/purchase')
@role_required('consumer')
def buy_items_in_cart(user_id):
    products = Purchase.query.filter_by(user_id=user_id, is_purchased=False).all()

    if not products:
        return jsonify({'message': 'Cart is empty'}), 400

    purchase_data = []
    for product in products:
        purchase_data.append({
            'product_id': product.product_id,
            'quantity': product.quantity,
            'price': product.price,
            'producer_id': product.producer_id,
            'name': product.product_name
        })
    
    # purchase_data = json.dumps(purchase_data)
    
    producer_url = 'http://host.docker.internal:8001/purchase'
    response = requests.post(producer_url, json=purchase_data)

    if response.status_code != 200 and response.status_code != 400:
        return jsonify({'message': 'Purchase request failed'}), 500

    response_data = response.json()

    if response_data['success']:
        # Purchase successful
        products = Purchase.query.filter_by(user_id=user_id, is_purchased=False).all()
        for product in products:
            product.is_purchased = True
        db.session.commit()
        return jsonify({'message': response_data['message']}), 200
    else:
        # Purchase failed, return an error message
        return jsonify({'message': response_data['message']}), 400


@app.route('/<int:user_id>/<int:producer_id>/products/<int:product_id>/offer', methods=['POST'])
@role_required('consumer')
def make_offer(user_id, producer_id, product_id):
    data = request.get_json()
    data["user_id"] = user_id
    data["producer_id"] = producer_id
    data["product_id"] = product_id
    data["send_to"] = "producer"
    data["status"] = "offer_by_consumer"
    print(data)

    url = 'your_own'
    connection = pika.BlockingConnection(pika.URLParameters(url))
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq_producer'))
    channel = connection.channel()
    channel.exchange_declare(exchange='alerts', exchange_type='topic')
    
    channel.basic_publish(exchange='alerts', routing_key="producer"+"."+str(producer_id), body=json.dumps(data))
    connection.close()
    return jsonify({'message': 'Offer sent.'}), 201


@app.route('/<int:user_id>/offers/<int:product_id>/accept', methods=['POST'])
@role_required('consumer')
def accept_offer(user_id, product_id):
    data = request.get_json()
    data["send_to"] = "producer"
    data["status"] = "accepted_by_consumer"
    product_name = data.get("product_name")
    price = data.get("price")
    quantity = data.get("quantity")
    producer_id = data.get("producer_id")

    in_cart = Purchase.query.filter_by(user_id=user_id, product_name=product_name, product_id=product_id, producer_id=producer_id, is_purchased=False).first()
    if in_cart:
        in_cart.price = price
        in_cart.quantity += quantity
    else:
        product = Purchase(product_name=product_name, price=price, quantity=quantity, product_id=product_id, user_id=user_id, producer_id=producer_id)
        db.session.add(product)
    db.session.commit()

    url = 'your_own'
    connection = pika.BlockingConnection(pika.URLParameters(url))
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq_producer'))
    channel = connection.channel()
    channel.exchange_declare(exchange='alerts', exchange_type='topic')

    channel.basic_publish(exchange='alerts', routing_key="producer"+"."+str(data.get("producer_id")), body=json.dumps(data))
    connection.close()
    return jsonify({'message': 'Product offer accepted and added to the cart.'}), 201



@app.route('/<int:user_id>/offers/<int:product_id>/decline', methods=['POST'])
@role_required('consumer')
def decline_offer(user_id, product_id):
    data = request.get_json()
    data["send_to"] = "producer"
    data["status"] = "declined_by_consumer"

    url = 'your_own'
    connection = pika.BlockingConnection(pika.URLParameters(url))
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq_producer'))
    channel = connection.channel()
    channel.exchange_declare(exchange='alerts', exchange_type='topic')

    channel.basic_publish(exchange='alerts', routing_key="producer"+"."+str(data.get("producer_id")), body=json.dumps(data))
    connection.close()
    return jsonify({'message': 'Offer declined.'}), 201


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8002)
