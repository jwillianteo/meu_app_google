import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

print("Iniciando script de reset do banco de dados...")
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("Erro: A variável DATABASE_URL não foi encontrada no arquivo .env")
else:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("Conectado ao banco de dados com sucesso!")

            # --- CORREÇÃO AQUI ---
            # Apagamos todas as tabelas usando CASCADE para remover dependências.
            # O SQLAlchemy criará todas novamente na ordem correta.
            sql_command = text('DROP TABLE IF EXISTS estudante, planilha, "user" CASCADE;')
            
            print(f"Executando comando para apagar tabelas: {sql_command}")
            connection.execute(sql_command)
            connection.commit()
            
            print("SUCESSO: Tabelas apagadas.")

    except Exception as e:
        print(f"ERRO: Ocorreu um erro: {e}")