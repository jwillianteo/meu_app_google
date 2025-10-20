# run.py
from app import create_app, db

# Cria a instância da aplicação a partir da factory
app = create_app()

# O comando 'flask run' ou o Gunicorn irá usar esta instância 'app'
if __name__ == '__main__':
    # Este bloco só será executado se você rodar 'python run.py' diretamente
    # Para produção, o Gunicorn é recomendado
    with app.app_context():
        # Garante que as tabelas do banco de dados sejam criadas se não existirem
        db.create_all()
    app.run(debug=False)