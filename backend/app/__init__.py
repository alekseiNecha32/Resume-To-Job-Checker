import os
from flask import Flask, app
from flask_cors import CORS
from dotenv import load_dotenv


from app.blueprints.authorization import auth_bp
from app.blueprints.api import api_bp
from app.blueprints.smart import smart_bp
from .blueprints.stripe import stripe_bp

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
                "supports_credentials": True,
                "methods": ["GET", "POST", "OPTIONS"],
                "expose_headers": ["Content-Type", "Authorization"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            }
        },
    )

    
    app.register_blueprint(api_bp)  
    app.register_blueprint(smart_bp)
    app.register_blueprint(stripe_bp)   
    app.register_blueprint(auth_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
