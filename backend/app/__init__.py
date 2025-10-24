import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

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
                "allow_headers": ["Content-Type"],
            }
        },
        supports_credentials=False,  
    )

    from app.blueprints.api import api_bp
    app.register_blueprint(api_bp)  # 

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app



 # CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173"]}})