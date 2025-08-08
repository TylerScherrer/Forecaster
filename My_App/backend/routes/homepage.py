from flask import Blueprint, jsonify

homepage = Blueprint("homepage", __name__)

@homepage.route("/")
def index():
    return jsonify(message="Hello from the Flask backend!")
