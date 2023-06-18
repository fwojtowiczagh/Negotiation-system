from flask import Flask, render_template, jsonify, flash
from flask_cors import CORS
from flask_sse import sse

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secretkey"
    CORS(app)

    from .views import auth, consumer, producer

    app.register_blueprint(consumer, url_prefix='/consumer')
    app.register_blueprint(auth)
    app.register_blueprint(producer)


    @app.route('/', methods=['GET'])
    def base():
        return jsonify({"Hello": "yes"}), 201

    return app
