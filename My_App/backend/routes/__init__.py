from .homepage import homepage
from .store import store_bp


def register_routes(app):
    app.register_blueprint(homepage)
    app.register_blueprint(store_bp)
