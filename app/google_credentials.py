# app/google_credentials.py
import os
import json

# Define o nome do arquivo temporário que será usado em produção
TEMP_SECRET_FILE = '/tmp/client_secret.json'

def get_google_client_secret_path():
    """
    Verifica se as credenciais do Google estão em uma variável de ambiente (produção).
    Se estiverem, salva o conteúdo em um arquivo temporário e retorna o caminho.
    Caso contrário, retorna o caminho para o arquivo local (desenvolvimento).
    """
    # Tenta ler o conteúdo JSON da variável de ambiente 'GOOGLE_CLIENT_SECRET_JSON'
    json_content = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')

    if json_content:
        try:
            # Escreve o conteúdo JSON em um arquivo temporário que a biblioteca do Google pode ler
            with open(TEMP_SECRET_FILE, 'w') as f:
                f.write(json_content)
            # Retorna o caminho para este arquivo temporário
            return TEMP_SECRET_FILE
        except Exception as e:
            print(f"ERRO: Não foi possível escrever o arquivo de segredo temporário: {e}")
            return None
    else:
        # Se a variável de ambiente não existir, assume ambiente de desenvolvimento
        # e retorna o nome do arquivo local.
        return 'client_secret.json'