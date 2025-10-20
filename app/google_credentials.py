import os
import json

def get_google_client_secret():
    """
    Retorna o caminho para o arquivo client_secret.json, 
    criando-o a partir de uma variável de ambiente se estiver em produção.
    """
    # Tenta ler o conteúdo JSON da variável de ambiente (para produção no Render)
    json_content = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')

    if json_content:
        # Define um caminho temporário para salvar o arquivo de credenciais
        # Ambientes como o Render permitem escrita no diretório /tmp
        filepath = '/tmp/client_secret.json'
        with open(filepath, 'w') as f:
            f.write(json_content)
        return filepath
    
    # Se a variável de ambiente não existir, usa o arquivo local (para desenvolvimento)
    return 'client_secret.json'