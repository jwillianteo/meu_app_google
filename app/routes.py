import os
import json
import pandas as pd
import random
from flask import render_template, url_for, flash, redirect, request, Blueprint, session, jsonify
from app import db, bcrypt
from app.models import User, Planilha, Estudante
from app.utils import send_email, get_column_mapping_from_ai
from flask_login import login_user, current_user, logout_user, login_required
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sklearn.cluster import KMeans
from sklearn.preprocessing import OneHotEncoder
import warnings

# Suprimir avisos do oauthlib sobre mudanças de escopo
warnings.filterwarnings('ignore', message='.*scope.*')
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

main = Blueprint('main', __name__)


# --- ROTAS DE AUTENTICAÇÃO E USUÁRIO ---

@main.route("/")
@main.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            if not user.confirmed:
                flash('Sua conta ainda não foi confirmada. Por favor, verifique seu e-mail.', 'warning')
                return redirect(url_for('main.login'))

            token = user.get_reset_token()
            login_link = url_for('main.login_verify', token=token, _external=True)
            html_content = f'''
                <p>Olá {user.username},</p>
                <p>Para completar seu login, clique no link abaixo. Este link é válido por 30 minutos.</p>
                <a href="{login_link}">Completar Login</a>
                <p>Se você não tentou fazer este login, pode ignorar este e-mail com segurança.</p>
            '''
            send_email(user.email, 'Complete seu Login', html_content)

            session['user_id_to_verify'] = user.id
            return redirect(url_for('main.login_pending'))
        else:
            flash('Login falhou. Por favor, verifique seu e-mail e senha.', 'danger')
            
    return render_template('login.html', title='Login')


@main.route("/login/pending")
def login_pending():
    if 'user_id_to_verify' not in session:
        return redirect(url_for('main.login'))
    return render_template('verify_login.html', title="Verifique seu E-mail")


@main.route("/login/verify/<token>")
def login_verify(token):
    user_to_verify_id = session.get('user_id_to_verify')
    user = User.verify_reset_token(token)

    if user and user.id == user_to_verify_id:
        login_user(user, remember=True)
        session.pop('user_id_to_verify', None)
        flash('Login realizado com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    else:
        flash('O link de login é inválido ou expirou.', 'danger')
        return redirect(url_for('main.login'))


@main.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Este nome de usuário já está em uso. Por favor, escolha outro.', 'danger')
            return redirect(url_for('main.register'))
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Este endereço de e-mail já foi cadastrado.', 'danger')
            return redirect(url_for('main.register'))
            
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        token = user.get_reset_token()
        confirm_link = url_for('main.confirm_email', token=token, _external=True)
        html_content = f'<p>Bem-vindo! Por favor, confirme seu e-mail clicando no link: <a href="{confirm_link}">Confirmar E-mail</a></p>'
        send_email(user.email, 'Confirmação de Cadastro', html_content)
        
        flash('Uma mensagem de confirmação foi enviada para o seu e-mail. Por favor, confirme para poder fazer o login.', 'info')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Cadastro')


@main.route('/confirm/<token>')
def confirm_email(token):
    user = User.verify_reset_token(token)
    if user:
        if user.confirmed:
            flash('Esta conta já foi confirmada. Por favor, faça o login.', 'info')
        else:
            user.confirmed = True
            db.session.commit()
            flash('Sua conta foi confirmada com sucesso! Agora você pode fazer o login.', 'success')
    else:
        flash('O link de confirmação é inválido ou expirou.', 'danger')
    return redirect(url_for('main.login'))


@main.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            token = user.get_reset_token()
            reset_link = url_for('main.reset_token', token=token, _external=True)
            html_content = f'<p>Para resetar sua senha, visite o seguinte link: <a href="{reset_link}">{reset_link}</a></p>'
            send_email(user.email, 'Reset de Senha', html_content)
        flash('Se uma conta com este e-mail existir, um link para resetar a senha foi enviado.', 'info')
        return redirect(url_for('main.login'))
    return render_template('request_reset.html', title='Resetar Senha')


@main.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('O token é inválido ou expirou.', 'warning')
        return redirect(url_for('main.reset_request'))
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user.password_hash = hashed_password
        db.session.commit()
        flash('Sua senha foi atualizada! Você já pode fazer o login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('reset_token.html', title='Resetar Senha')


# --- ROTAS DE GERENCIAMENTO DE FORMS E DADOS ---

@main.route("/manage_sheets", methods=['GET', 'POST'])
@login_required
def manage_sheets():
    if request.method == 'POST':
        nome = request.form.get('nome_amigavel')
        sheet_id = request.form.get('spreadsheet_id')
        range_name = request.form.get('range_name')

        nova_planilha = Planilha(
            nome_amigavel=nome,
            spreadsheet_id=sheet_id,
            range_name=range_name,
            author=current_user
        )
        db.session.add(nova_planilha)
        db.session.commit()
        flash('Novo formulário adicionado com sucesso!', 'success')
        return redirect(url_for('main.manage_sheets'))

    planilhas_do_usuario = Planilha.query.filter_by(user_id=current_user.id).all()
    return render_template('manage_sheets.html', title="Gerenciar Formulários", planilhas=planilhas_do_usuario)


@main.route("/search_sheets")
@login_required
def search_sheets():
    """Busca Google Forms na conta do usuário"""
    if not current_user.google_credentials:
        flash('Por favor, conecte sua conta Google primeiro.', 'warning')
        return redirect(url_for('main.dashboard'))

    try:
        creds_data = json.loads(current_user.google_credentials)
        creds = Credentials.from_authorized_user_info(creds_data)
        
        if creds.expired and creds.refresh_token:
            print("Token expirado, fazendo refresh...")
            creds.refresh(Request())
            current_user.google_credentials = creds.to_json()
            db.session.commit()
            print("Token atualizado com sucesso!")
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.form'",
            pageSize=50,
            fields="nextPageToken, files(id, name, modifiedTime, webViewLink)",
            orderBy="modifiedTime desc"
        ).execute()
        
        forms = results.get('files', [])
        
        if not forms:
            print("Nenhum formulário encontrado no Drive")
            flash('Nenhum Google Forms foi encontrado na sua conta.', 'info')
            return render_template('search_results.html', 
                                 title="Selecione um Formulário", 
                                 spreadsheets=[])
        
        print(f"Encontrados {len(forms)} formulários no Drive")
        
        forms_service = build('forms', 'v1', credentials=creds)
        forms_with_responses = []
        
        # Buscar também planilhas disponíveis para vínculo manual
        sheets_results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.spreadsheet'",
            pageSize=20,
            fields="nextPageToken, files(id, name, modifiedTime)",
            orderBy="modifiedTime desc"
        ).execute()
        
        available_sheets = sheets_results.get('files', [])
        
        for form in forms:
            try:
                form_info = forms_service.forms().get(formId=form['id']).execute()
                
                if 'linkedSheetId' in form_info:
                    sheet_id = form_info['linkedSheetId']
                    form['response_sheet_id'] = sheet_id
                    forms_with_responses.append(form)
                    print(f"Formulário '{form['name']}' tem planilha de respostas: {sheet_id}")
                else:
                    form['response_sheet_id'] = None
                    forms_with_responses.append(form)
                    print(f"Formulário '{form['name']}' não tem planilha de respostas vinculada")
                    
            except Exception as e:
                print(f"Erro ao buscar info do formulário {form['name']}: {e}")
                form['response_sheet_id'] = None
                forms_with_responses.append(form)
        
        return render_template('search_results.html', 
                             title="Selecione um Formulário", 
                             spreadsheets=forms_with_responses,
                             available_sheets=available_sheets)

    except Exception as e:
        print(f"--- ERRO DETALHADO AO BUSCAR FORMULÁRIOS ---")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print(f"------------------------------------------")
        
        if "invalid_grant" in str(e) or "Token has been expired" in str(e):
            current_user.google_credentials = None
            db.session.commit()
            flash('Sua sessão do Google expirou. Por favor, reconecte sua conta.', 'warning')
            return redirect(url_for('main.authorize_google'))
        
        flash(f'Erro ao buscar formulários: {str(e)}. Tente reconectar sua conta Google.', 'danger')
        return redirect(url_for('main.manage_sheets'))


@main.route("/create_and_link_sheet/<form_id>", methods=['POST'])
@login_required
def create_and_link_sheet(form_id):
    """
    Cria uma nova Planilha Google e tenta vincular a um formulário existente.
    Se não conseguir vincular automaticamente, fornece instruções para vínculo manual.
    """
    if not current_user.google_credentials:
        flash('Sua conta Google não está conectada.', 'warning')
        return redirect(url_for('main.search_sheets'))
        
    try:
        creds = Credentials.from_authorized_user_info(json.loads(current_user.google_credentials))
        
        # 1. Obter o nome do formulário para usar no título da planilha
        forms_service = build('forms', 'v1', credentials=creds)
        form = forms_service.forms().get(formId=form_id).execute()
        form_title = form.get('info', {}).get('title', 'Respostas de Formulário Sem Título')
        form_url = f"https://docs.google.com/forms/d/{form_id}/edit"

        # 2. Criar uma nova planilha usando a API do Google Sheets
        sheets_service = build('sheets', 'v4', credentials=creds)
        spreadsheet_body = {
            'properties': {'title': f"{form_title} (Respostas)"}
        }
        new_sheet = sheets_service.spreadsheets().create(body=spreadsheet_body).execute()
        new_sheet_id = new_sheet['spreadsheetId']
        new_sheet_url = f"https://docs.google.com/spreadsheets/d/{new_sheet_id}/edit"
        print(f"Planilha '{new_sheet['properties']['title']}' criada com ID: {new_sheet_id}")

        # 3. Tentar vincular usando batchUpdate (método documentado)
        try:
            update_request = {
                "requests": [{
                    "createDestination": {
                        "destination": {
                            "spreadsheetDestination": {
                                "spreadsheetId": new_sheet_id
                            }
                        }
                    }
                }]
            }
            
            result = forms_service.forms().batchUpdate(
                formId=form_id, 
                body=update_request
            ).execute()
            
            print(f"Planilha vinculada com sucesso ao formulário ID: {form_id}")
            flash('Planilha de respostas criada e vinculada com sucesso!', 'success')
            
        except Exception as link_error:
            print(f"Vínculo automático falhou: {link_error}")
            # Se o vínculo automático falhar, salvar as informações para vínculo manual
            session['pending_link'] = {
                'form_id': form_id,
                'form_title': form_title,
                'form_url': form_url,
                'sheet_id': new_sheet_id,
                'sheet_title': new_sheet['properties']['title'],
                'sheet_url': new_sheet_url
            }
            
            flash('A planilha foi criada, mas o vínculo automático falhou. Siga as instruções para vincular manualmente.', 'warning')
            
            return redirect(url_for('main.link_instructions'))

    except Exception as e:
        print(f"--- ERRO AO CRIAR PLANILHA ---")
        print(f"Erro: {e}")
        import traceback
        print(traceback.format_exc())
        flash(f'Erro ao criar planilha: {e}', 'danger')

    return redirect(url_for('main.search_sheets'))


@main.route("/link_instructions")
@login_required
def link_instructions():
    """Página com instruções detalhadas para vincular planilha manualmente"""
    pending_link = session.get('pending_link')
    if not pending_link:
        return redirect(url_for('main.search_sheets'))
    
    return render_template('link_instructions.html', 
                         title="Instruções para Vincular Planilha",
                         pending_link=pending_link)


@main.route("/manual_link_form/<form_id>", methods=['POST'])
@login_required
def manual_link_form(form_id):
    """
    Rota alternativa para vincular manualmente uma planilha existente a um formulário
    """
    if not current_user.google_credentials:
        flash('Sua conta Google não está conectada.', 'warning')
        return redirect(url_for('main.search_sheets'))
    
    try:
        sheet_id = request.form.get('sheet_id')
        if not sheet_id:
            flash('ID da planilha é obrigatório.', 'danger')
            return redirect(url_for('main.search_sheets'))
            
        creds = Credentials.from_authorized_user_info(json.loads(current_user.google_credentials))
        forms_service = build('forms', 'v1', credentials=creds)
        
        # Obter informações do formulário para mostrar ao usuário
        form = forms_service.forms().get(formId=form_id).execute()
        form_title = form.get('info', {}).get('title', 'Formulário Sem Título')
        form_url = f"https://docs.google.com/forms/d/{form_id}/edit"
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        
        # Tentar o vínculo automático
        try:
            update_request = {
                "requests": [{
                    "createDestination": {
                        "destination": {
                            "spreadsheetDestination": {
                                "spreadsheetId": sheet_id
                            }
                        }
                    }
                }]
            }
            
            result = forms_service.forms().batchUpdate(
                formId=form_id, 
                body=update_request
            ).execute()
            
            flash('Planilha vinculada manualmente com sucesso!', 'success')
            
        except Exception as link_error:
            print(f"Vínculo automático falhou: {link_error}")
            # Se falhar, fornecer instruções
            flash(
                f'📝 Para vincular manualmente:<br>'
                f'1. Acesse o <a href="{form_url}" target="_blank">Google Forms: {form_title}</a><br>'
                f'2. Clique em "Respostas" → Ícone do Sheets<br>'
                f'3. Selecione "Selecionar planilha de respostas existente"<br>'
                f'4. Encontre e selecione a planilha com ID: <code>{sheet_id}</code><br><br>'
                f'🔗 <a href="{sheet_url}" target="_blank">Abrir Planilha</a>', 
                'warning'
            )
        
    except Exception as e:
        print(f"Erro no vínculo manual: {e}")
        flash(f'Erro ao processar vínculo manual: {e}', 'danger')
    
    return redirect(url_for('main.search_sheets'))


@main.route("/select_form/<form_id>/<sheet_id>", methods=['POST'])
@login_required
def select_form(form_id, sheet_id):
    """Seleciona um formulário e redireciona para o dashboard"""
    try:
        nome_formulario = request.form.get('nome_formulario')
        
        planilha_existente = Planilha.query.filter_by(
            spreadsheet_id=sheet_id,
            user_id=current_user.id
        ).first()
        
        if planilha_existente:
            session['selected_form_id'] = planilha_existente.id
            flash(f'Formulário "{nome_formulario}" já estava cadastrado e foi selecionado!', 'info')
        else:
            nova_planilha = Planilha(
                nome_amigavel=nome_formulario,
                spreadsheet_id=sheet_id,
                range_name="Respostas ao formulário 1!A:Z", 
                author=current_user
            )
            db.session.add(nova_planilha)
            db.session.commit()
            
            session['selected_form_id'] = nova_planilha.id
            flash(f'Formulário "{nome_formulario}" foi adicionado e selecionado!', 'success')
        
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        print(f"Erro ao selecionar formulário: {e}")
        flash(f'Erro ao selecionar formulário: {str(e)}', 'danger')
        return redirect(url_for('main.search_sheets'))


@main.route("/view_sheet_data/<int:planilha_id>")
@login_required
def view_sheet_data(planilha_id):
    planilha = Planilha.query.get_or_404(planilha_id)

    if planilha.author != current_user:
        flash('Você não tem permissão para ver este formulário.', 'danger')
        return redirect(url_for('main.manage_sheets'))

    if not current_user.google_credentials:
        flash('Por favor, conecte sua conta Google primeiro.', 'warning')
        return redirect(url_for('main.dashboard'))

    creds = Credentials.from_authorized_user_info(json.loads(current_user.google_credentials))

    try:
        service = build('sheets', 'v4', credentials=creds)

        spreadsheet_id = planilha.spreadsheet_id
        range_name = planilha.range_name

        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                    range=range_name).execute()
        values = result.get('values', [])

        return jsonify(nome_da_planilha=planilha.nome_amigavel, data=values)

    except Exception as e:
        print(f"--- ERRO DETALHADO DA API DO GOOGLE ---")
        print(e)
        print(f"------------------------------------")
        return jsonify(error=str(e)), 500


@main.route("/process_sheet/<int:planilha_id>")
@login_required
def process_sheet(planilha_id):
    planilha = Planilha.query.get_or_404(planilha_id)
    if planilha.author != current_user:
        flash('Você não tem permissão para processar este formulário.', 'danger')
        return redirect(url_for('main.manage_sheets'))

    creds = Credentials.from_authorized_user_info(json.loads(current_user.google_credentials))
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=planilha.spreadsheet_id,
                                range=planilha.range_name).execute()
    values = result.get('values', [])

    if not values or len(values) < 2:
        flash('Nenhum dado encontrado no formulário para processar.', 'warning')
        return redirect(url_for('main.manage_sheets'))

    Estudante.query.filter_by(planilha_origem_id=planilha.id).delete()
    db.session.commit()

    header = values[0]
    data_rows = values[1:]
    
    column_map = get_column_mapping_from_ai(header)
    
    # VALIDAÇÃO MAIS FLEXÍVEL: apenas 'nome' é obrigatório
    if not column_map or column_map.get('nome') is None:
        flash('Não foi possível identificar a coluna "nome" no formulário. Verifique se o formulário tem uma pergunta com o nome da pessoa.', 'danger')
        return redirect(url_for('main.manage_sheets'))
    
    # Se não tiver 'curso_interesse', usa um valor padrão
    if column_map.get('curso_interesse') is None:
        print("⚠️ 'curso_interesse' não encontrado. Usando valor padrão.")
        usar_padrao_curso = True
    else:
        usar_padrao_curso = False

    estudantes_processados = 0
    for row in data_rows:
        try:
            # Campo obrigatório
            nome_estudante = row[column_map['nome']] if len(row) > column_map['nome'] else None
            if not nome_estudante:
                continue
            
            # Campos opcionais
            idade_estudante = None
            if column_map.get('idade') is not None and len(row) > column_map['idade']:
                try:
                    idade_estudante = int(row[column_map['idade']])
                except (ValueError, TypeError):
                    pass
            
            cidade_estudante = None
            if column_map.get('cidade') is not None and len(row) > column_map['cidade']:
                cidade_estudante = row[column_map['cidade']]
            
            # Curso de interesse (obrigatório no modelo, mas flexível)
            if usar_padrao_curso:
                curso_interesse_estudante = "Não especificado"
            else:
                col_idx = column_map.get('curso_interesse')
                if col_idx is not None and len(row) > col_idx:
                    curso_interesse_estudante = row[col_idx]
                else:
                    curso_interesse_estudante = "Não especificado"
            
            dispositivo_simulado = random.choice(['Desktop', 'Mobile', 'Mobile', 'Mobile'])

            novo_estudante = Estudante(
                nome=nome_estudante,
                idade=idade_estudante,
                cidade=cidade_estudante,
                curso_interesse=curso_interesse_estudante,
                dispositivo_acesso=dispositivo_simulado,
                planilha_origem_id=planilha.id,
                user_id=current_user.id
            )
            db.session.add(novo_estudante)
            estudantes_processados += 1

        except (IndexError, ValueError, KeyError) as e:
            print(f"Linha ignorada: {row} | Erro: {e}")
            continue

    db.session.commit()
    
    if estudantes_processados > 0:
        flash(f'{estudantes_processados} respostas processadas com sucesso!', 'success')
    else:
        flash('Nenhuma resposta válida foi encontrada.', 'warning')
    
    return redirect(url_for('main.view_processed_data'))


@main.route("/webhook/new_response/<int:planilha_id>/<secret_key>", methods=['POST'])
def webhook_new_response(planilha_id, secret_key):
    if secret_key != os.environ.get('WEBHOOK_SECRET_KEY'):
        return jsonify(status="error", message="Chave secreta inválida"), 403

    data = request.json
    if not data or 'values' not in data:
        return jsonify(status="error", message="Dados ausentes"), 400

    row_values = data['values']
    header_values = data.get('header', [])

    planilha = Planilha.query.get(planilha_id)
    if not planilha:
        return jsonify(status="error", message="ID de formulário não encontrado"), 404

    column_map = get_column_mapping_from_ai(header_values)
    if not column_map or column_map.get('nome') is None or column_map.get('curso_interesse') is None:
         column_map = {'nome': 1, 'idade': 2, 'cidade': 3, 'curso_interesse': 4}

    try:
        nome = row_values[column_map['nome']]
        curso = row_values[column_map['curso_interesse']]
        idade = int(row_values[column_map.get('idade')]) if column_map.get('idade') is not None else None
        cidade = row_values[column_map.get('cidade')] if column_map.get('cidade') is not None else None
        dispositivo = random.choice(['Desktop', 'Mobile', 'Mobile'])

        novo_estudante = Estudante(
            nome=nome,
            idade=idade,
            cidade=cidade,
            curso_interesse=curso,
            dispositivo_acesso=dispositivo,
            planilha_origem_id=planilha.id,
            user_id=planilha.user_id
        )
        db.session.add(novo_estudante)
        db.session.commit()
        
        print(f"Novo estudante '{nome}' adicionado via webhook com sucesso!")
        return jsonify(status="success", message="Registro adicionado")

    except Exception as e:
        print(f"Erro no webhook ao processar linha: {row_values} | Erro: {e}")
        return jsonify(status="error", message=f"Erro ao processar: {e}"), 500


@main.route("/view_processed_data")
@login_required
def view_processed_data():
    estudantes = Estudante.query.filter_by(user_id=current_user.id).order_by(Estudante.nome).all()
    return render_template('processed_data.html', title="Dados Processados", estudantes=estudantes)


@main.route("/analysis")
@login_required
def analysis():
    query = Estudante.query.filter_by(user_id=current_user.id).statement
    try:
        df = pd.read_sql(query, db.engine)
    except Exception as e:
        print(f"Erro ao ler dados do DB com Pandas: {e}")
        df = pd.DataFrame()

    if df.empty:
        flash('Não há dados processados para analisar. Processe um formulário primeiro.', 'warning')
        return redirect(url_for('main.dashboard'))

    # Tratamento para colunas que podem não existir ou serem nulas
    df['idade'] = pd.to_numeric(df['idade'], errors='coerce')
    
    popularidade_cursos = df['curso_interesse'].value_counts().to_dict()
    alunos_por_cidade = df['cidade'].value_counts().to_dict()
    idade_media_por_curso = df.groupby('curso_interesse')['idade'].mean().round(1).to_dict()
    idade_media_geral = round(df['idade'].mean(), 1) if not df['idade'].isnull().all() else 0
    acesso_por_dispositivo = df['dispositivo_acesso'].value_counts().to_dict()

    return render_template('analysis.html', 
                           title="Análise de Dados",
                           popularidade_cursos=popularidade_cursos,
                           alunos_por_cidade=alunos_por_cidade,
                           idade_media_por_curso=idade_media_por_curso,
                           idade_media_geral=idade_media_geral,
                           total_estudantes=len(df),
                           acesso_por_dispositivo=acesso_por_dispositivo)


@main.route("/ml_analysis")
@login_required
def ml_analysis():
    query = Estudante.query.filter_by(user_id=current_user.id).statement
    df = pd.read_sql(query, db.engine)

    if len(df) < 3:
        flash('Você precisa de pelo menos 3 registros de estudantes para realizar a análise de ML.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    # --- CORREÇÃO APLICADA AQUI ---
    # Tratamento de dados nulos mais robusto para evitar NaN no K-Means
    
    # Converte 'idade' para numérico, forçando erros a virarem NaN
    df['idade'] = pd.to_numeric(df['idade'], errors='coerce')
    
    # Calcula a mediana (mais robusta a outliers que a média)
    idade_mediana = df['idade'].median()
    
    # Preenche os valores nulos com a mediana. Se a mediana for NaN (caso todas as idades sejam nulas),
    # usa um valor padrão (ex: 20).
    df['idade'].fillna(idade_mediana if pd.notna(idade_mediana) else 20, inplace=True)

    df['cidade'] = df['cidade'].fillna('Desconhecida')
    df['curso_interesse'] = df['curso_interesse'].fillna('Não especificado')

    features = df[['idade', 'cidade', 'curso_interesse']]
    encoder = OneHotEncoder(handle_unknown='ignore')
    features_encoded = encoder.fit_transform(features[['cidade', 'curso_interesse']])
    
    features_final = pd.concat([
        features[['idade']].reset_index(drop=True),
        pd.DataFrame(features_encoded.toarray())
    ], axis=1)
    features_final.columns = features_final.columns.astype(str)

    # O n_init='auto' ou um número como 10 é importante para o comportamento futuro do scikit-learn
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['segmento'] = kmeans.fit_predict(features_final)

    segmentos_info = []
    for i in range(3):
        df_segmento = df[df['segmento'] == i]
        
        if not df_segmento.empty:
            idade_media = round(df_segmento['idade'].mean(), 1)
            # Usa .mode()[0] para pegar o valor mais frequente.
            curso_principal = df_segmento['curso_interesse'].mode()[0]
            cidade_principal = df_segmento['cidade'].mode()[0]
            total_alunos = len(df_segmento)
            
            descricao = (f"Este segmento contém {total_alunos} aluno(s). O perfil principal é de estudantes "
                         f"com idade média de {idade_media} anos, vindo principalmente de {cidade_principal} "
                         f"e com maior interesse no curso de {curso_principal}.")
            
            segmentos_info.append({
                "id": i,
                "total": total_alunos,
                "descricao": descricao,
                "alunos": df_segmento.to_dict(orient='records')
            })

    return render_template('ml_analysis.html', title="Análise com Machine Learning", segmentos=segmentos_info)


# --- ROTAS DE AUTORIZAÇÃO COM GOOGLE ---

@main.route("/authorize_google")
@login_required
def authorize_google():
    SCOPES = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/forms.body.readonly',
        'https://www.googleapis.com/auth/forms.responses.readonly',
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/forms.body'
    ]
    
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=url_for('main.google_callback', _external=True)
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    session['google_oauth_state'] = state
    return redirect(authorization_url)


@main.route("/google_callback")
@login_required
def google_callback():
    state = session.get('google_oauth_state')
    
    SCOPES = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/forms.body.readonly',
        'https://www.googleapis.com/auth/forms.responses.readonly',
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/forms.body'
    ]
    
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('main.google_callback', _external=True)
    )

    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        current_user.email = user_info.get('email', current_user.email)
        
        current_user.google_credentials = credentials.to_json()
        db.session.commit()
        
        flash('Sua conta Google foi conectada com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        print(f"Erro durante callback do Google: {e}")
        import traceback
        print(traceback.format_exc())
        flash('Erro ao conectar com o Google. Por favor, tente novamente.', 'danger')
        return redirect(url_for('main.dashboard'))


# --- ROTAS GERAIS ---

@main.route("/disconnect_google")
@login_required
def disconnect_google():
    current_user.google_credentials = None
    db.session.commit()
    flash('Sua conta Google foi desconectada com sucesso.', 'success')
    return redirect(url_for('main.dashboard'))


@main.route("/logout")
def logout():
    logout_user()
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('main.login'))


@main.route("/dashboard")
@login_required
def dashboard():
    # Estatísticas para o dashboard
    total_formularios = Planilha.query.filter_by(user_id=current_user.id).count()
    total_estudantes = Estudante.query.filter_by(user_id=current_user.id).count()
    
    # Últimos formulários
    ultimos_formularios = Planilha.query.filter_by(user_id=current_user.id).order_by(Planilha.data_cadastro.desc()).limit(5).all()
    
    # Formulário selecionado na sessão
    selected_form = None
    if 'selected_form_id' in session:
        selected_form = Planilha.query.get(session['selected_form_id'])
    
    # Inicializa as variáveis do gráfico como None fora do bloco try
    grafico_labels = None
    grafico_values = None

    if total_estudantes > 0:
        try:
            query = Estudante.query.filter_by(user_id=current_user.id).statement
            df = pd.read_sql(query, db.engine)
            if not df.empty and 'curso_interesse' in df.columns:
                cursos_populares = df['curso_interesse'].value_counts().head(5)
                
                # Passa os dados como listas separadas para o template
                grafico_labels = cursos_populares.index.tolist()
                grafico_values = cursos_populares.tolist() 
            
        except Exception as e:
            print(f"Erro ao processar dados para gráfico: {e}")
            # Garante que as variáveis permaneçam None em caso de erro
            grafico_labels = None
            grafico_values = None
    
    return render_template('dashboard.html', 
                         title="Dashboard",
                         total_formularios=total_formularios,
                         total_estudantes=total_estudantes,
                         ultimos_formularios=ultimos_formularios,
                         selected_form=selected_form,
                         grafico_labels=grafico_labels,
                         grafico_values=grafico_values)


# --- ROTA PARA LIMPAR DADOS ---
@main.route("/clear_data", methods=['POST'])
@login_required
def clear_data():
    """Limpa todos os estudantes e planilhas do usuário"""
    try:
        estudantes_deletados = Estudante.query.filter_by(user_id=current_user.id).delete()
        planilhas_deletadas = Planilha.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        session.pop('selected_form_id', None)
        flash(f'{estudantes_deletados} registros de estudantes e {planilhas_deletadas} formulários foram removidos.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao limpar dados: {str(e)}', 'danger')
    
    return redirect(url_for('main.dashboard'))


# --- ROTA PARA TESTE DE EMAIL ---
@main.route("/test_email")
@login_required
def test_email():
    """Rota para testar o envio de emails"""
    try:
        html_content = '''
            <h1>Teste de Email</h1>
            <p>Este é um email de teste do sistema de análise de formulários.</p>
            <p>Se você recebeu este email, o sistema de envio está funcionando corretamente.</p>
        '''
        send_email(current_user.email, 'Teste de Email - Sistema de Análise', html_content)
        flash('Email de teste enviado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao enviar email de teste: {str(e)}', 'danger')
    
    return redirect(url_for('main.dashboard'))


# --- ROTA DE SAÚDE DO SISTEMA ---
@main.route("/health")
def health_check():
    """Rota para verificar a saúde do sistema"""
    try:
        # Testar conexão com o banco
        db.session.execute('SELECT 1')
        db_status = 'OK'
        
        # Testar se as credenciais do Google estão configuradas
        google_status = 'OK' if os.path.exists('client_secret.json') else 'Client Secret não encontrado'
        
        # Testar variáveis de ambiente
        webhook_secret = 'Configurado' if os.environ.get('WEBHOOK_SECRET_KEY') else 'Não configurado'
        email_config = 'Configurado' if os.environ.get('MAIL_USERNAME') else 'Não configurado'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'google_credentials': google_status,
            'webhook_secret': webhook_secret,
            'email_config': email_config,
            'timestamp': pd.Timestamp.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': pd.Timestamp.now().isoformat()
        }), 500

