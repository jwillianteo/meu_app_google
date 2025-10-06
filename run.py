# run.py

from app import create_app, db

# Cria a instância da nossa aplicação
app = create_app()

if __name__ == '__main__':
    # Este bloco garante que o banco de dados e as tabelas
    # sejam criados antes da primeira requisição, se não existirem.
    with app.app_context():
        db.create_all()
    
    # Inicia o servidor de desenvolvimento
    app.run(debug=True)