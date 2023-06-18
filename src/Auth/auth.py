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


app = Flask(__name__)
app.config["SECRET_KEY"] = "secretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = 'mysql://root:root@db_auth/auth'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)


@dataclass
class User(db.Model):
    id: int
    username: str
    password: str
    email: str
    role: str

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), nullable=False)


@app.route('/producers')
def read_producers():
    producers = User.query.filter_by(role="Producer").with_entities(User.id, User.username).all()
    if not producers:
        return jsonify({'message': 'No producers'}), 400
    return jsonify(producers), 200


@app.route('/allpass')
def allpass():
    products = User.query.all()
    return jsonify(products)


@app.route('/<int:id>/delete', methods=['DELETE'])
def delete_product(id):
    user = User.query.filter_by(id=id).first()
    if not user:
        return jsonify({'message': 'No such product in the cart'}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'Product successfully deleted.'})


@app.route('/signup', methods=['POST'])
def signup():
    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')
    role = request.json.get('role')

    if not username or not password or not email:
        return jsonify({'message': 'Fill in all credentials!'}), 400

    taken_username = User.query.filter_by(username=username).first()
    taken_email = User.query.filter_by(email=email).first()
    if taken_email or taken_username:
        return jsonify({'message': 'Credentials already taken!'}), 400

    user = User(username=username, password=password, email=email, role=role)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User created successfully!'}), 201


@app.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')

    if not email or not password:
        return jsonify({'message': 'Username and password are required!'}), 400

    # check if the user exists
    user = User.query.filter_by(email=email).first()

    if not user or user.password != password:
        return jsonify({'message': 'Invalid login or password!'}), 400

    token_payload = {"sub": user.id, "username": user.username, "exp": datetime.utcnow() + timedelta(days=1), "role": user.role}
    access_token = jwt.encode(token_payload, app.config["SECRET_KEY"], algorithm="HS256")

    return jsonify({"access_token": access_token}), 200


@app.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Successfully logged out'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8004)
