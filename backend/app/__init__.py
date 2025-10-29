import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from app.blueprints.api import api_bp
from app.blueprints.smart import smart_bp
from app.blueprints.authorization import auth_bp as auth_api_bp

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-User-Id"],
                "expose_headers": ["Authorization"]
            }
        },
        supports_credentials=False,
    )

    
    app.register_blueprint(api_bp)  # 
    app.register_blueprint(smart_bp)
    app.register_blueprint(auth_api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app



 # CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173"]}})