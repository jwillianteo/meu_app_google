#!/usr/bin/env bash
# Este script executa durante a fase de build na plataforma de hospedagem

# Sai imediatamente se um comando falhar
set -o errexit

# 1. Instala todas as dependências do Python
echo "Instalando dependências..."
pip install -r requirements.txt

# 2. Cria as tabelas do banco de dados diretamente
echo "Criando tabelas do banco de dados..."
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

echo "Build finalizado com sucesso!"