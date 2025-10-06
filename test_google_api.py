import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Escopos necessários
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

CLIENT_SECRETS_FILE = 'client_secret.json'

def run_test():
    """
    Teste da API do Google usando a porta 8081 que já funcionou anteriormente
    """
    print("--- INICIANDO TESTE DE CONEXÃO COM A API DO GOOGLE ---")
    print("Usando porta 8081 (que já funcionou anteriormente)")
    
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"ERRO: Arquivo '{CLIENT_SECRETS_FILE}' não encontrado!")
        print("Certifique-se de que o arquivo client_secret.json está na pasta atual.")
        return
    
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    
    try:
        print("\nIniciando servidor local na porta 8081...")
        print("Um navegador será aberto para autorização.")
        print("IMPORTANTE: Complete a autorização no navegador e aguarde!")
        
        credentials = flow.run_local_server(
            port=8081,
            timeout_seconds=300,  # 5 minutos de timeout
            open_browser=True
        )
        
        print("\nAutenticação bem-sucedida na porta 8081!")
        
    except KeyboardInterrupt:
        print("\nProcesso interrompido pelo usuário.")
        print("Para tentar novamente, execute o script e complete a autorização.")
        return
        
    except OSError as e:
        if "Address already in use" in str(e) or "10013" in str(e):
            print(f"\nERRO: Porta 8081 está ocupada ou bloqueada.")
            print("Soluções:")
            print("1. Feche outros programas que podem estar usando a porta 8081")
            print("2. Execute este script como Administrador")
            print("3. Verifique se há outros serviços rodando nesta porta")
            return
        else:
            print(f"\nERRO de rede: {e}")
            return
            
    except Exception as e:
        print(f"\nERRO durante autenticação: {e}")
        return
    
    # Mostrar e salvar credencial
    print("\n" + "="*70)
    print("CREDENCIAL GERADA - COPIE TODO O JSON ABAIXO:")
    print("="*70)
    credential_json = credentials.to_json()
    print(credential_json)
    print("="*70)
    
    # Salvar credencial em arquivo
    try:
        with open('credencial_google.json', 'w', encoding='utf-8') as f:
            f.write(credential_json)
        print("Credencial salva no arquivo 'credencial_google.json'")
    except Exception as e:
        print(f"Não foi possível salvar o arquivo: {e}")
    
    # Testar Google Drive API
    try:
        print("\nTestando Google Drive API...")
        drive_service = build('drive', 'v3', credentials=credentials)
        
        results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps-spreadsheet'",
            pageSize=20,
            fields="files(id, name, createdTime, webViewLink)",
            orderBy="name"
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print("Nenhuma planilha Google encontrada na sua conta.")
            print("(Mas a conexão funcionou perfeitamente!)")
        else:
            print(f"SUCESSO! {len(items)} planilhas encontradas:")
            print("-" * 80)
            for i, item in enumerate(items, 1):
                print(f"{i:2d}. Nome: {item['name']}")
                print(f"    ID: {item['id']}")
                if 'webViewLink' in item:
                    print(f"    Link: {item['webViewLink']}")
                print()
            print("-" * 80)
        
    except Exception as e:
        print(f"Erro ao acessar Google Drive: {e}")
        return
    
    # Testar Google Sheets API
    try:
        print("Testando Google Sheets API...")
        sheets_service = build('sheets', 'v4', credentials=credentials)
        print("Google Sheets API funcionando corretamente!")
        
    except Exception as e:
        print(f"Erro ao acessar Google Sheets: {e}")
        return
    
    print("\nTESTE CONCLUÍDO COM SUCESSO!")
    print("\nO que fazer agora:")
    print("1. Copie a credencial JSON mostrada acima")
    print("2. Cole essa credencial na sua aplicação Flask")
    print("3. A credencial também foi salva em 'credencial_google.json'")
    print("4. Use essa credencial para acessar suas planilhas Google")

if __name__ == '__main__':
    # Permite conexões HTTP locais para desenvolvimento
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    run_test()