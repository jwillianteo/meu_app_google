import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def testar_com_compartilhados():
    """
    Testa incluindo arquivos compartilhados e drives compartilhados
    """
    
    try:
        with open('credencial_google.json', 'r') as f:
            cred_data = json.load(f)
        print("Credencial carregada.")
    except FileNotFoundError:
        print("ERRO: Execute primeiro o test_google_api.py")
        return
    
    credentials = Credentials.from_authorized_user_info(cred_data)
    service = build('drive', 'v3', credentials=credentials)
    
    print("="*70)
    print("DIAGNÓSTICO COMPLETO DO GOOGLE DRIVE")
    print("="*70)
    
    # Informações da conta
    try:
        about = service.about().get(fields="user").execute()
        user_info = about.get('user', {})
        print(f"Usuário autenticado: {user_info.get('emailAddress', 'Não disponível')}")
        print(f"Nome: {user_info.get('displayName', 'Não disponível')}")
        print()
    except Exception as e:
        print(f"Não foi possível obter informações do usuário: {e}\n")
    
    # 1. ARQUIVOS PRÓPRIOS (MEU DRIVE)
    print("1. ARQUIVOS NO MEU DRIVE (não compartilhados):")
    print("-" * 70)
    try:
        results = service.files().list(
            q="'me' in owners",
            pageSize=20,
            fields="files(id, name, mimeType)",
            orderBy="modifiedTime desc"
        ).execute()
        
        my_files = results.get('files', [])
        if my_files:
            print(f"Encontrados {len(my_files)} arquivos próprios:")
            for item in my_files[:10]:
                print(f"  - {item['name']} ({item['mimeType']})")
        else:
            print("Nenhum arquivo próprio encontrado.")
    except Exception as e:
        print(f"Erro: {e}")
    
    print("\n" + "="*70)
    
    # 2. PLANILHAS PRÓPRIAS
    print("2. PLANILHAS GOOGLE SHEETS (MINHAS):")
    print("-" * 70)
    try:
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.spreadsheet' and 'me' in owners",
            pageSize=20,
            fields="files(id, name, webViewLink)"
        ).execute()
        
        my_sheets = results.get('files', [])
        if my_sheets:
            print(f"Encontradas {len(my_sheets)} planilhas próprias:")
            for sheet in my_sheets:
                print(f"  - {sheet['name']}")
                print(f"    ID: {sheet['id']}")
                print(f"    Link: {sheet.get('webViewLink', 'N/A')}")
                print()
        else:
            print("Nenhuma planilha Google Sheets própria encontrada.")
    except Exception as e:
        print(f"Erro: {e}")
    
    print("="*70)
    
    # 3. ARQUIVOS COMPARTILHADOS COMIGO
    print("3. ARQUIVOS COMPARTILHADOS COMIGO:")
    print("-" * 70)
    try:
        results = service.files().list(
            q="sharedWithMe=true",
            pageSize=20,
            fields="files(id, name, mimeType, owners)",
            orderBy="modifiedTime desc"
        ).execute()
        
        shared_files = results.get('files', [])
        if shared_files:
            print(f"Encontrados {len(shared_files)} arquivos compartilhados:")
            for item in shared_files[:10]:
                owner = "N/A"
                if 'owners' in item and item['owners']:
                    owner = item['owners'][0].get('emailAddress', 'N/A')
                print(f"  - {item['name']}")
                print(f"    Proprietário: {owner}")
                print(f"    Tipo: {item['mimeType']}")
                print()
        else:
            print("Nenhum arquivo compartilhado encontrado.")
    except Exception as e:
        print(f"Erro: {e}")
    
    print("="*70)
    
    # 4. TODAS AS PLANILHAS (INCLUINDO COMPARTILHADAS)
    print("4. TODAS AS PLANILHAS (PRÓPRIAS + COMPARTILHADAS):")
    print("-" * 70)
    try:
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.spreadsheet'",
            pageSize=30,
            fields="files(id, name, webViewLink, owners, shared)",
            orderBy="modifiedTime desc"
        ).execute()
        
        all_sheets = results.get('files', [])
        if all_sheets:
            print(f"TOTAL DE PLANILHAS ENCONTRADAS: {len(all_sheets)}")
            print()
            for i, sheet in enumerate(all_sheets, 1):
                owner_email = "N/A"
                if 'owners' in sheet and sheet['owners']:
                    owner_email = sheet['owners'][0].get('emailAddress', 'N/A')
                
                is_shared = sheet.get('shared', False)
                status = "COMPARTILHADA" if is_shared else "PRÓPRIA"
                
                print(f"{i}. {sheet['name']} [{status}]")
                print(f"   Proprietário: {owner_email}")
                print(f"   ID: {sheet['id']}")
                print(f"   Link: {sheet.get('webViewLink', 'N/A')}")
                print()
        else:
            print("NENHUMA PLANILHA ENCONTRADA (nem próprias, nem compartilhadas)!")
            print()
            print("POSSÍVEIS CAUSAS:")
            print("1. Você se autenticou com uma conta diferente")
            print("2. As planilhas estão em um Google Workspace diferente")
            print("3. As permissões da API não estão corretas")
            print("4. As planilhas foram deletadas recentemente")
    except Exception as e:
        print(f"Erro ao buscar todas as planilhas: {e}")
    
    print("\n" + "="*70)
    print("DIAGNÓSTICO FINALIZADO")
    print("="*70)

if __name__ == '__main__':
    testar_com_compartilhados()