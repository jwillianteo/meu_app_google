from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Descomente a linha abaixo apenas na primeira vez que rodar
        # ou se precisar recriar o banco de dados.
        # db.create_all()
        pass
    app.run(debug=True) # Use debug=False em produção