# /backend/wsgi.py
from run import app  # or from your module where "app = Flask(__name__)" lives
# Azure/Gunicorn looks for "app"
