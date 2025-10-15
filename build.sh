#!/usr/bin/env bash
# Este script executa durante a fase de build na plataforma de hospedagem

# Sai imediatamente se um comando falhar
set -o errexit

# 1. Instala todas as dependências do Python
echo "Instalando dependências..."
pip install -r requirements.txt

# 2. Executa as migrações do banco de dados
echo "Executando migrações do banco de dados..."
flask db upgrade

echo "Build finalizado com sucesso!"