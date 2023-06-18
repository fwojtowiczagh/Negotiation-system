from dataclasses import dataclass
from flask import Flask, jsonify, abort, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_cors import CORS
# from flask_script import Manager
import requests
import jwt
from datetime import datetime, timedelta
from functools import wraps
import pika
import json


app = Flask(__name__)
app.config["SECRET_KEY"] = "secretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = 'mysql://root:root@db_negotiator/negotiator'
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


@dataclass
class Offer(db.Model):
    id: int
    user_id: int
    producer_id: int
    product_id: int
    product_name: str
    price: int
    send_to: str
    status: str

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    producer_id = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    send_to = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(200), nullable=False)


@app.route('/producers/<int:user_id>/offers')
@role_required('producer')
def producer_offers(user_id):
    offers = Offer.query.filter_by(producer_id=user_id).all()
    if not offers:
        return jsonify({'message': 'No offers'}), 400
    return jsonify(offers), 200


@app.route('/consumers/<int:user_id>/offers')
@role_required('consumer')
def consumer_offers(user_id):
    offers = Offer.query.filter_by(user_id=user_id).all()
    if not offers:
        return jsonify({'message': 'No offers'}), 400
    return jsonify(offers), 200


@app.route('/allpass')
def allpass():
    products = Offer.query.all()
    return jsonify(products)


@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_offer(id):
    product = Offer.query.filter_by(id=id).first()
    if not product:
        return jsonify({'message': 'No such product in the cart'}), 400
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product successfully deleted from cart.'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8003)
