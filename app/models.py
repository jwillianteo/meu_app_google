from app import db, login_manager
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    google_credentials = db.Column(db.Text, nullable=True)
    
    planilhas = db.relationship('Planilha', backref='author', lazy=True)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)
        
    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Planilha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_amigavel = db.Column(db.String(100), nullable=False)
    spreadsheet_id = db.Column(db.String(100), nullable=False)
    range_name = db.Column(db.String(100), nullable=False)
    data_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Planilha('{self.nome_amigavel}', '{self.spreadsheet_id}')"

class Estudante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    idade = db.Column(db.Integer, nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    curso_interesse = db.Column(db.String(100), nullable=False)
    
    # --- COLUNAS "IoT" ATUALIZADAS ---
    timestamp_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    dispositivo_acesso = db.Column(db.String(50), nullable=True)

    # Chaves estrangeiras
    planilha_origem_id = db.Column(db.Integer, db.ForeignKey('planilha.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Estudante('{self.nome}', '{self.curso_interesse}')"