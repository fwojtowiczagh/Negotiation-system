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
import time


app = Flask(__name__)
# app.register_blueprint(sse, url_prefix='/stream')
app.config["SECRET_KEY"] = "secretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = 'mysql://root:root@db_producer/producer'
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
                elif user_role == role and ('producer_id' not in kwargs or user_id == kwargs.get('producer_id')):
                    return f(*args, **kwargs)
                else:
                    return jsonify({'message': 'Insufficient privileges'}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Token has expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'message': 'Invalid token'}), 401

        return decorated_function
    return decorator


@dataclass
class Product(db.Model):
    id: int
    name: str
    price: int
    quantity: int
    producer_id: int

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    producer_id = db.Column(db.Integer, nullable=False)


@app.route('/')
def read_producers():
    return jsonify({'message': 'hello from producer'}), 200


@app.route('/<int:producer_id>/products')
@role_required('allaccess')
def read_products(producer_id):
    products = Product.query.filter_by(producer_id=producer_id).all()
    if not products:
        return jsonify({'message': 'No products in store'}), 400
    return jsonify(products), 200


@app.route('/<int:producer_id>/products', methods=['POST'])
@role_required('producer')
def create_product(producer_id):
    name = request.json.get("name")
    price = request.json.get("price")
    quantity = request.json.get("quantity")

    in_store = Product.query.filter_by(name=name, producer_id=producer_id).first()
    # in_store = Product.query.filter_by(name=name, price=price, producer_id=producer_id).first()
    if in_store:
        if in_store.price != price:
            jsonify({'message': 'Product with the same name and different price already exists.'}), 400
        else:
            in_store.quantity += quantity
    else:
        product = Product(name=name, price=price, quantity=quantity, producer_id=producer_id)
        db.session.add(product)
    db.session.commit()
    return jsonify({'message': 'Product successfully added.'}), 201


@app.route('/<int:producer_id>/products/<int:product_id>')
@role_required('allaccess')
def read_product(producer_id, product_id):
    product = Product.query.filter_by(producer_id=producer_id, id=product_id).first()
    if not product:
        return jsonify({'message': 'No product in the store'}), 400
    return jsonify(product), 200


@app.route('/<int:producer_id>/products/<int:product_id>', methods=['PUT'])
@role_required('producer')
def update_product(producer_id, product_id):
    data = request.get_json()  # block id change!

    # product = Product.query.get(product_id)
    product = Product.query.filter_by(producer_id=producer_id, id=product_id).first()
    if not product:
        return jsonify({'message': 'No such product in the store'}), 400

    if data.get("name"):
        product_same_name = Product.query.filter_by(producer_id=producer_id, name=data.get("name")).first()
        if product_same_name:
            return jsonify({'message': 'Product with that name already exists'}), 400

    for key, value in data.items():
        setattr(product, key, value)
    db.session.commit()
    return jsonify({'message': 'Product successfully updated.'}), 200


@app.route('/<int:producer_id>/products/<int:product_id>', methods=['DELETE'])
@role_required('producer')
def delete_product(producer_id, product_id):
    product = Product.query.filter_by(producer_id=producer_id, id=product_id).first()
    # print(product)
    if not product:
        return jsonify({'message': 'No such product in the cart'}), 400
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product successfully deleted.'}), 200


@app.route('/purchase', methods=['POST'])
def sell_products():
    purchase_data = request.get_json()

    try:
        # with db.session.begin_nested():  # it creates nested transactions within the loop and make them all behave separately
        for purchase_item in purchase_data:
            product_id = purchase_item.get('product_id')
            quantity = purchase_item.get('quantity')
            price = purchase_item.get('price')
            producer_id = purchase_item.get('producer_id')
            name = purchase_item.get('name')

            product = Product.query.filter_by(id=product_id).first()
            if product is None:
                raise Exception(f'Product with name {name} not found')

            if (product.price != price or product.name != name):
                raise Exception(f'Product with name {name} not found')

            if quantity > product.quantity:
                raise Exception(f'Insufficient quantity for product with name {name}')

            product.quantity -= quantity
            if product.quantity <= 0:
                product.quantity = 0

        db.session.commit()
        return jsonify({'success': True, 'message': 'Purchase successful'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/<int:producer_id>/offers/<int:offer_id>/counteroffer', methods=['POST'])
@role_required('producer')
def make_counter_offer(producer_id, offer_id):
    data = request.get_json()
    data["send_to"] = "consumer"
    data["status"] = "offer_by_producer"
    
    url = 'your_own'
    connection = pika.BlockingConnection(pika.URLParameters(url))
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq_producer', 5672))  # works, but first docker-compose only the queue!
    channel = connection.channel()
    channel.exchange_declare(exchange='alerts', exchange_type='topic')

    channel.basic_publish(exchange='alerts', routing_key="consumer"+"."+str(data.get('user_id')), body=json.dumps(data))
    connection.close()
    return jsonify({'message': 'Product counter offer sent.'}), 201


@app.route('/<int:producer_id>/offers/<int:offer_id>/accept', methods=['POST'])
@role_required('producer')
def accept_offer(producer_id, offer_id):
    data = request.get_json()
    data["send_to"] = "consumer"
    data["status"] = "accepted_by_producer"

    url = 'your_own'
    connection = pika.BlockingConnection(pika.URLParameters(url))
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq_producer', 5672))  # works, but first docker-compose only the queue!
    channel = connection.channel()
    channel.exchange_declare(exchange='alerts', exchange_type='topic')

    channel.basic_publish(exchange='alerts', routing_key="consumer"+"."+str(data.get('user_id')), body=json.dumps(data))
    connection.close()
    return jsonify({'message': 'Product offer accepted.'}), 201



@app.route('/<int:producer_id>/offers/<int:offer_id>/decline', methods=['POST'])
@role_required('producer')
def decline_offer(producer_id, offer_id):
    data = request.get_json()
    data["send_to"] = "consumer"
    data["status"] = "declined_by_producer"

    url = 'your_own'
    connection = pika.BlockingConnection(pika.URLParameters(url))
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq_producer', 5672))  # works, but first docker-compose only the queue!
    channel = connection.channel()
    channel.exchange_declare(exchange='alerts', exchange_type='topic')

    channel.basic_publish(exchange='alerts', routing_key="consumer"+"."+str(data.get('user_id')), body=json.dumps(data))
    connection.close()
    return jsonify({'message': 'Offer declined.'}), 201


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8001)
