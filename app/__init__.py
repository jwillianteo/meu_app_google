from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Desativa o cache de arquivos estáticos em desenvolvimento
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app