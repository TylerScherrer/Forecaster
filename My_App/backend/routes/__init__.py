# backend/routes/__init__.py
from .homepage import homepage
from .stores import store_bp
from .forecast import forecast_bp
from .explain_forecast import explain_bp
from .data_access import _ensure_required_objects

def register_routes(app):
    app.register_blueprint(homepage)
    app.register_blueprint(store_bp)
    app.register_blueprint(forecast_bp)
    app.register_blueprint(explain_bp)

    # NEW: pre-warm data/model one time at boot
    with app.app_context():
        _ensure_required_objects(app.config)
