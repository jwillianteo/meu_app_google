import os
import json
import random
from app import create_app, db
from app.models import User, Planilha, Estudante
from app.utils import get_column_mapping_from_ai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def sync_all_sheets():
    """
    Esta função busca todas as planilhas cadastradas no sistema
    e atualiza os dados de estudantes no banco de dados.
    """
    app = create_app()
    with app.app_context():
        print("--- INICIANDO SCRIPT DE SINCRONIZAÇÃO ---")
        
        todas_as_planilhas = Planilha.query.all()
        if not todas_as_planilhas:
            print("Nenhuma planilha cadastrada para sincronizar. Finalizando.")
            return

        print(f"Encontradas {len(todas_as_planilhas)} planilhas para verificar.")

        for planilha in todas_as_planilhas:
            print(f"\n--- Processando planilha: '{planilha.nome_amigavel}' (ID: {planilha.id}) ---")
            
            user = User.query.get(planilha.user_id)
            if not user or not user.google_credentials:
                print(f"Usuário da planilha não encontrado ou não tem credenciais Google. Pulando...")
                continue

            try:
                creds = Credentials.from_authorized_user_info(json.loads(user.google_credentials))
                service = build('sheets', 'v4', credentials=creds)
                sheet = service.spreadsheets()
                result = sheet.values().get(spreadsheetId=planilha.spreadsheet_id,
                                            range=planilha.range_name).execute()
                values = result.get('values', [])
            except Exception as e:
                print(f"ERRO ao buscar dados da planilha no Google. Pulando. Detalhes: {e}")
                continue

            if not values or len(values) < 2:
                print("Planilha vazia ou sem dados suficientes. Pulando.")
                continue

            print("Dados encontrados. Iniciando processamento e salvamento...")
            Estudante.query.filter_by(planilha_origem_id=planilha.id).delete()
            
            header = values[0]
            data_rows = values[1:]
            
            column_map = get_column_mapping_from_ai(header)
            if not column_map or column_map.get('nome') is None:
                print("IA não conseguiu mapear colunas. Usando fallback manual.")
                # Este mapeamento assume a ordem: Nome, Idade, Cidade, Curso. Ajuste se necessário.
                column_map = {'nome': 0, 'idade': 1, 'cidade': 2, 'curso_interesse': 3}

            estudantes_processados = 0
            for row in data_rows:
                try:
                    novo_estudante = Estudante(
                        nome=row[column_map['nome']],
                        idade=int(row[column_map['idade']]) if column_map.get('idade') is not None and row[column_map['idade']] else None,
                        cidade=row[column_map['cidade']] if column_map.get('cidade') is not None and row[column_map['cidade']] else None,
                        curso_interesse=row[column_map['curso_interesse']] if column_map.get('curso_interesse') is not None else "Não informado",
                        dispositivo_acesso=random.choice(['Desktop', 'Mobile']),
                        planilha_origem_id=planilha.id,
                        user_id=user.id
                    )
                    db.session.add(novo_estudante)
                    estudantes_processados += 1
                except (IndexError, ValueError, KeyError) as e:
                    print(f"Linha ignorada por erro de formato ou mapeamento: {row} | Erro: {e}")
                    continue
            
            db.session.commit()
            print(f"SUCESSO: {estudantes_processados} registros processados para a planilha '{planilha.nome_amigavel}'.")

        print("\n--- SCRIPT DE SINCRONIZAÇÃO FINALIZADO ---")

# Esta parte permite que o script seja executado diretamente pelo terminal
if __name__ == '__main__':
    sync_all_sheets()