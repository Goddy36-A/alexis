from flask import Flask
from .database import init_db

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'cfnd-secret-2025-ideawood'
    app.config['DATABASE'] = 'cfnd.db'

    init_db(app)

    from .routes import main
    from .auth import auth
    from .api import api
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(api, url_prefix='/api')

    return app
