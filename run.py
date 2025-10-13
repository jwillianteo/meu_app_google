# run.py
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Altere esta linha
    app.run(debug=False)