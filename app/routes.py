import os
import json
import pandas as pd
import random
from flask import render_template, url_for, flash, redirect, request, Blueprint, session
from app import db, bcrypt
from app.models import User, Planilha, Estudante
from app.utils import send_email, get_column_mapping_from_ai, gerar_insights_com_ia, preparar_dados_graficos
from flask_login import login_user, current_user, logout_user, login_required
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sklearn.cluster import KMeans
from sklearn.preprocessing import OneHotEncoder
import warnings

# Importa a nova função para carregar as credenciais do Google
from app.google_credentials import get_google_client_secret_path

# Configurações iniciais
warnings.filterwarnings('ignore', message='.*scope.*')
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/forms.body.readonly',
    'https://www.googleapis.com/auth/forms.responses.readonly', 'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/forms.body'
]

main = Blueprint('main', __name__)

def get_scheme():
    return 'https' if 'RENDER' in os.environ else 'http'

# --- ROTAS DE AUTENTICAÇÃO, LOGOUT E RESET DE SENHA ---
@main.route("/")
def home():
    return redirect(url_for('main.login'))

@main.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            if not user.confirmed:
                flash('Sua conta não foi confirmada. Verifique seu e-mail.', 'warning')
                return redirect(url_for('main.login'))
            login_user(user, remember=True)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Login falhou. Verifique seu e-mail e senha.', 'danger')
    return render_template('login.html', title='Login')

@main.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Você foi desconectado com segurança.', 'info')
    return redirect(url_for('main.login'))

@main.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username, email = request.form.get('username'), request.form.get('email')
        if User.query.filter_by(username=username).first():
            flash('Este nome de usuário já está em uso.', 'danger')
            return redirect(url_for('main.register'))
        if User.query.filter_by(email=email).first():
            flash('Este e-mail já foi cadastrado.', 'danger')
            return redirect(url_for('main.register'))
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        token = user.get_reset_token()
        confirm_link = url_for('main.confirm_email', token=token, _external=True, _scheme=get_scheme())
        send_email(user.email, 'Confirmação de Cadastro', f'<p>Bem-vindo! Confirme seu e-mail clicando aqui: <a href="{confirm_link}">Confirmar</a></p>')
        flash('Um e-mail de confirmação foi enviado. Por favor, confirme para poder fazer o login.', 'info')
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

# --- ROTAS DE RESET DE SENHA (NOVAS) ---
@main.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    """Rota para o usuário solicitar o e-mail de reset de senha."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user:
            token = user.get_reset_token()
            reset_link = url_for('main.reset_token', token=token, _external=True, _scheme=get_scheme())
            send_email(user.email, 'Redefinição de Senha', f'<p>Para redefinir sua senha, visite o seguinte link: <a href="{reset_link}">Redefinir Senha</a></p>')
        flash('Se uma conta com este e-mail existir, um link para redefinir a senha foi enviado.', 'info')
        return redirect(url_for('main.login'))
    return render_template('request_reset.html', title='Resetar Senha')

@main.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    """Rota para o usuário inserir a nova senha após clicar no link do e-mail."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('O link é inválido ou expirou.', 'warning')
        return redirect(url_for('main.reset_request'))
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        user.password_hash = hashed_password
        db.session.commit()
        flash('Sua senha foi atualizada! Você já pode fazer o login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('reset_token.html', title='Resetar Senha')


# --- ROTAS DE AUTORIZAÇÃO COM GOOGLE (CORRIGIDAS) ---
@main.route("/authorize_google")
@login_required
def authorize_google():
    client_secret_path = get_google_client_secret_path()
    if not client_secret_path or not os.path.exists(client_secret_path):
        flash('Erro de configuração do servidor: credenciais do Google não encontradas.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    redirect_uri = url_for('main.google_callback', _external=True, _scheme=get_scheme())
    flow = Flow.from_client_secrets_file(client_secret_path, scopes=SCOPES, redirect_uri=redirect_uri)
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
    session['google_oauth_state'] = state
    return redirect(authorization_url)

@main.route("/google_callback")
@login_required
def google_callback():
    client_secret_path = get_google_client_secret_path()
    if not client_secret_path:
        flash('Erro de configuração do servidor ao processar o callback do Google.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    state = session.get('google_oauth_state')
    redirect_uri = url_for('main.google_callback', _external=True, _scheme=get_scheme())
    flow = Flow.from_client_secrets_file(client_secret_path, scopes=SCOPES, state=state, redirect_uri=redirect_uri)
    
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        google_email = build('oauth2', 'v2', credentials=credentials).userinfo().get().execute().get('email')

        existing_user = User.query.filter(User.email == google_email, User.id != current_user.id).first()
        if existing_user:
            flash(f'O e-mail do Google "{google_email}" já está associado a outra conta.', 'danger')
            return redirect(url_for('main.dashboard'))

        current_user.google_credentials = credentials.to_json()
        db.session.commit()
        flash('Sua conta Google foi conectada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao conectar com o Google: {e}', 'danger')
    return redirect(url_for('main.dashboard'))

# --- ROTAS DE GERENCIAMENTO DE PLANILHAS E DADOS ---
@main.route("/manage_sheets", methods=['GET', 'POST'])
@login_required
def manage_sheets():
    if request.method == 'POST':
        nova_planilha = Planilha(
            nome_amigavel=request.form.get('nome_amigavel'),
            spreadsheet_id=request.form.get('spreadsheet_id'),
            range_name=request.form.get('range_name'),
            author=current_user
        )
        db.session.add(nova_planilha)
        db.session.commit()
        flash('Novo formulário adicionado com sucesso!', 'success')
        return redirect(url_for('main.manage_sheets'))
    planilhas_do_usuario = Planilha.query.filter_by(user_id=current_user.id).all()
    return render_template('manage_sheets.html', title="Gerenciar Formulários", planilhas=planilhas_do_usuario)

@main.route("/remove_sheet/<int:planilha_id>", methods=['POST'])
@login_required
def remove_sheet(planilha_id):
    planilha = Planilha.query.get_or_404(planilha_id)
    if planilha.author != current_user:
        flash('Você não tem permissão para remover este formulário.', 'danger')
        return redirect(url_for('main.manage_sheets'))
    try:
        Estudante.query.filter_by(planilha_origem_id=planilha.id).delete()
        db.session.delete(planilha)
        db.session.commit()
        flash(f'O formulário "{planilha.nome_amigavel}" foi desconectado e seus dados removidos do sistema.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao remover o formulário: {e}', 'danger')
    return redirect(url_for('main.manage_sheets'))

@main.route("/search_sheets")
@login_required
def search_sheets():
    if not current_user.google_credentials:
        flash('Por favor, conecte sua conta Google primeiro.', 'warning')
        return redirect(url_for('main.dashboard'))
    try:
        creds = Credentials.from_authorized_user_info(json.loads(current_user.google_credentials))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            current_user.google_credentials = creds.to_json()
            db.session.commit()
        drive_service = build('drive', 'v3', credentials=creds)
        results = drive_service.files().list(q="mimeType='application/vnd.google-apps.form'", pageSize=50, fields="files(id, name, modifiedTime, webViewLink)", orderBy="modifiedTime desc").execute()
        forms = results.get('files', [])
        if not forms:
            flash('Nenhum Google Forms foi encontrado na sua conta.', 'info')
            return render_template('search_results.html', title="Selecione um Formulário", spreadsheets=[])
        forms_service = build('forms', 'v1', credentials=creds)
        forms_with_responses = []
        for form in forms:
            try:
                form_info = forms_service.forms().get(formId=form['id']).execute()
                form['response_sheet_id'] = form_info.get('linkedSheetId')
                forms_with_responses.append(form)
            except Exception as e:
                print(f"Erro ao buscar info do formulário {form['name']}: {e}")
                form['response_sheet_id'] = None
                forms_with_responses.append(form)
        return render_template('search_results.html', title="Selecione um Formulário", spreadsheets=forms_with_responses)
    except Exception as e:
        if "invalid_grant" in str(e) or "Token has been expired" in str(e):
            current_user.google_credentials = None
            db.session.commit()
            flash('Sua sessão do Google expirou. Por favor, reconecte sua conta.', 'warning')
            return redirect(url_for('main.authorize_google'))
        flash(f'Erro ao buscar formulários: {e}. Tente reconectar sua conta Google.', 'danger')
        return redirect(url_for('main.manage_sheets'))

@main.route("/select_form/<form_id>/<sheet_id>", methods=['POST'])
@login_required
def select_form(form_id, sheet_id):
    try:
        nome_formulario = request.form.get('nome_formulario')
        if Planilha.query.filter_by(spreadsheet_id=sheet_id, user_id=current_user.id).first():
            flash(f'Formulário "{nome_formulario}" já estava cadastrado!', 'info')
        else:
            nova_planilha = Planilha(nome_amigavel=nome_formulario, spreadsheet_id=sheet_id, range_name="Respostas ao formulário 1!A:Z", author=current_user)
            db.session.add(nova_planilha)
            db.session.commit()
            flash(f'Formulário "{nome_formulario}" foi adicionado e selecionado!', 'success')
        return redirect(url_for('main.manage_sheets'))
    except Exception as e:
        flash(f'Erro ao selecionar formulário: {e}', 'danger')
        return redirect(url_for('main.search_sheets'))

@main.route("/process_sheet/<int:planilha_id>")
@login_required
def process_sheet(planilha_id):
    planilha = Planilha.query.get_or_404(planilha_id)
    if planilha.author != current_user:
        return redirect(url_for('main.manage_sheets'))
    creds = Credentials.from_authorized_user_info(json.loads(current_user.google_credentials))
    service = build('sheets', 'v4', credentials=creds)
    values = service.spreadsheets().values().get(spreadsheetId=planilha.spreadsheet_id, range=planilha.range_name).execute().get('values', [])
    if not values or len(values) < 2:
        flash('Nenhum dado encontrado no formulário para processar.', 'warning')
        return redirect(url_for('main.manage_sheets'))
    Estudante.query.filter_by(planilha_origem_id=planilha.id).delete()
    db.session.commit()
    header = values[0]
    column_map = get_column_mapping_from_ai(header)
    if not column_map or column_map.get('nome') is None:
        flash('Não foi possível identificar a coluna "nome" no formulário.', 'danger')
        return redirect(url_for('main.manage_sheets'))
    estudantes_processados = 0
    for row in values[1:]:
        try:
            db.session.add(Estudante(
                nome=row[column_map['nome']],
                idade=int(row[column_map['idade']]) if column_map.get('idade') is not None and len(row) > column_map['idade'] and row[column_map['idade']].isdigit() else None,
                cidade=row[column_map['cidade']] if column_map.get('cidade') is not None and len(row) > column_map['cidade'] else None,
                curso_interesse=row[column_map['curso_interesse']] if column_map.get('curso_interesse') is not None and len(row) > column_map['curso_interesse'] else "Não especificado",
                dispositivo_acesso=random.choice(['Desktop', 'Mobile']),
                planilha_origem_id=planilha.id,
                user_id=current_user.id
            ))
            estudantes_processados += 1
        except (IndexError, ValueError, KeyError) as e:
            print(f"Linha ignorada: {row} | Erro: {e}")
            continue
    db.session.commit()
    flash(f'{estudantes_processados} respostas processadas com sucesso!', 'success' if estudantes_processados > 0 else 'warning')
    return redirect(url_for('main.view_processed_data'))

@main.route("/view_processed_data")
@login_required
def view_processed_data():
    estudantes = Estudante.query.filter_by(user_id=current_user.id).order_by(Estudante.nome).all()
    return render_template('processed_data.html', title="Dados Processados", estudantes=estudantes)

@main.route("/analysis")
@login_required
def analysis():
    df = pd.read_sql(Estudante.query.filter_by(user_id=current_user.id).statement, db.engine)
    if df.empty:
        flash('Não há dados processados para analisar.', 'warning')
        return redirect(url_for('main.dashboard'))
    df['idade'] = pd.to_numeric(df['idade'], errors='coerce')
    return render_template('analysis.html', title="Análise de Dados",
                           popularidade_cursos=df['curso_interesse'].value_counts().to_dict(),
                           alunos_por_cidade=df['cidade'].value_counts().to_dict(),
                           idade_media_por_curso=df.groupby('curso_interesse')['idade'].mean().round(1).to_dict(),
                           idade_media_geral=round(df['idade'].mean(), 1) if not df['idade'].isnull().all() else 0,
                           total_estudantes=len(df),
                           acesso_por_dispositivo=df['dispositivo_acesso'].value_counts().to_dict())

@main.route("/ml_analysis")
@login_required
def ml_analysis():
    df = pd.read_sql(Estudante.query.filter_by(user_id=current_user.id).statement, db.engine)
    if len(df) < 3:
        flash('Você precisa de pelo menos 3 registros de estudantes para a análise de ML.', 'warning')
        return redirect(url_for('main.dashboard'))
    df['idade'] = pd.to_numeric(df['idade'], errors='coerce').fillna(df['idade'].median() if pd.notna(df['idade'].median()) else 20)
    df.fillna({'cidade': 'Desconhecida', 'curso_interesse': 'Não especificado'}, inplace=True)
    df['timestamp_cadastro'] = pd.to_datetime(df['timestamp_cadastro'])
    features = df[['idade', 'cidade', 'curso_interesse']]
    encoder = OneHotEncoder(handle_unknown='ignore')
    features_encoded = encoder.fit_transform(features[['cidade', 'curso_interesse']])
    features_final = pd.concat([features[['idade']].reset_index(drop=True), pd.DataFrame(features_encoded.toarray(), columns=encoder.get_feature_names_out())], axis=1)
    num_clusters = min(3, len(df.drop_duplicates(subset=['id'])))
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    df['segmento'] = kmeans.fit_predict(features_final)
    segmentos_info = []
    dados_para_ia = {'total_estudantes': len(df), 'idade_media_geral': round(df['idade'].mean(), 1), 'cursos_populares': df['curso_interesse'].value_counts().head(3).to_dict(), 'cidades_principais': df['cidade'].value_counts().head(3).to_dict(), 'segmentos': []}
    for i in range(num_clusters):
        df_segmento = df[df['segmento'] == i]
        if not df_segmento.empty:
            segmento_data = {'id': i, 'total': len(df_segmento), 'idade_media': round(df_segmento['idade'].mean(), 1), 'curso_principal': df_segmento['curso_interesse'].mode()[0], 'cidade_principal': df_segmento['cidade'].mode()[0], 'alunos': df_segmento.to_dict(orient='records')}
            segmentos_info.append(segmento_data)
            dados_para_ia['segmentos'].append({'id': i + 1, 'total_alunos': len(df_segmento), 'idade_media': round(df_segmento['idade'].mean(), 1), 'curso_principal': df_segmento['curso_interesse'].mode()[0], 'cidade_principal': df_segmento['cidade'].mode()[0]})
    insights_ia = gerar_insights_com_ia(dados_para_ia)
    graficos_data = preparar_dados_graficos(df, segmentos_info)
    return render_template('ml_analysis_enhanced.html', title="Análise ML com IA", segmentos=segmentos_info, insights_ia=insights_ia, graficos_data=graficos_data, total_estudantes=len(df))

@main.route("/disconnect_google")
@login_required
def disconnect_google():
    current_user.google_credentials = None
    db.session.commit()
    flash('Sua conta Google foi desconectada.', 'info')
    return redirect(url_for('main.dashboard'))

@main.route("/dashboard")
@login_required
def dashboard():
    total_formularios = Planilha.query.filter_by(user_id=current_user.id).count()
    total_estudantes = Estudante.query.filter_by(user_id=current_user.id).count()
    ultimos_formularios = Planilha.query.filter_by(user_id=current_user.id).order_by(Planilha.data_cadastro.desc()).limit(5).all()
    grafico_labels, grafico_values = [], []
    if total_estudantes > 0:
        df = pd.read_sql(Estudante.query.filter_by(user_id=current_user.id).statement, db.engine)
        if not df.empty and 'curso_interesse' in df.columns:
            cursos_populares = df['curso_interesse'].value_counts().head(5)
            grafico_labels = cursos_populares.index.tolist()
            grafico_values = cursos_populares.values.tolist()
    return render_template('dashboard.html', title="Dashboard",
                         total_formularios=total_formularios,
                         total_estudantes=total_estudantes,
                         ultimos_formularios=ultimos_formularios,
                         grafico_labels=grafico_labels,
                         grafico_values=grafico_values)