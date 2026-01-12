import os
import logging
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from app.routes.export_docx import export_bp

from app.blueprints.authorization import auth_bp
from app.blueprints.api import api_bp
from app.blueprints.smart import smart_bp
from .blueprints.stripe import stripe_bp
from openai import OpenAI

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

    # Reduce noisy logs from httpx/stripe
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("stripe").setLevel(logging.WARNING)

    openai_key = os.getenv("OPENAI_API_KEY")
    app.config["OPENAI_CLIENT"] = OpenAI(api_key=openai_key) if openai_key else None
    app.logger.info("OpenAI configured: %s", bool(openai_key))


    CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://resume-to-job-checker-5.onrender.com",
                "https://www.resume-constructor.com",
                "https://resume-constructor.com",
                
               
            ],
            "supports_credentials": True,
            "methods": ["GET", "POST", "OPTIONS"],
            "expose_headers": ["Content-Type", "Authorization"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        },
    },
)

    
    app.register_blueprint(api_bp)  
    app.register_blueprint(smart_bp)
    app.register_blueprint(stripe_bp)   
    app.register_blueprint(auth_bp)
    app.register_blueprint(export_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
