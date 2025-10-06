Guia Completo de Instalação e Configuração do Sistema de Análise de Dados
📋 Pré-requisitos
Antes de começar, certifique-se de ter instalado:

Python 3.8+ (Download aqui)
PostgreSQL (Download aqui)
Git (opcional, para clonar repositórios)
Conta Google (para integração com Google Forms/Sheets)


🚀 Passo 1: Preparação do Ambiente
1.1 Criar uma pasta para o projeto
bashmkdir meu-projeto-analise
cd meu-projeto-analise
1.2 Criar ambiente virtual Python
Windows:
bashpython -m venv venv
venv\Scripts\activate
Linux/Mac:
bashpython3 -m venv venv
source venv/bin/activate
Você verá (venv) no início da linha do terminal, indicando que o ambiente está ativo.

📦 Passo 2: Instalar Dependências
2.1 Criar o arquivo requirements.txt
Copie o conteúdo do arquivo fornecido e salve como requirements.txt na pasta do projeto.
2.2 Instalar as bibliotecas
bashpip install -r requirements.txt
Aguarde alguns minutos enquanto todas as dependências são baixadas e instaladas.

🔐 Passo 3: Configurar o Banco de Dados PostgreSQL
3.1 Criar o banco de dados
Abra o pgAdmin ou o terminal do PostgreSQL e execute:
sqlCREATE DATABASE meu_banco_dados;
3.2 Criar usuário (se necessário)
sqlCREATE USER meu_usuario WITH PASSWORD 'minha_senha_segura';
GRANT ALL PRIVILEGES ON DATABASE meu_banco_dados TO meu_usuario;
3.3 Anotar a URL de conexão
A URL terá este formato:
postgresql://meu_usuario:minha_senha_segura@localhost:5432/meu_banco_dados

🔑 Passo 4: Configurar as Credenciais do Google
4.1 Acessar o Google Cloud Console

Acesse: https://console.cloud.google.com/
Faça login com sua conta Google
Clique em "Selecionar projeto" → "Novo Projeto"
Nomeie o projeto (ex: "Analise de Dados PI4")
Clique em "Criar"

4.2 Ativar as APIs necessárias

No menu lateral, vá em "APIs e Serviços" → "Biblioteca"
Busque e ative as seguintes APIs:

✅ Google Drive API
✅ Google Sheets API
✅ Google Forms API



4.3 Criar credenciais OAuth 2.0

Vá em "APIs e Serviços" → "Credenciais"
Clique em "+ CRIAR CREDENCIAIS" → "ID do cliente OAuth"
Configure a tela de consentimento:

Tipo: Externo
Nome do aplicativo: "Meu Sistema de Análise"
E-mail de suporte: seu e-mail
Domínios autorizados: deixe vazio por enquanto
Escopos: adicione os escopos do Google Drive e Sheets
Salve e continue


Criar o ID do cliente OAuth:

Tipo de aplicativo: Aplicativo da Web
Nome: "Cliente Web Flask"
URIs de redirecionamento autorizados:



     http://localhost:5000/google_callback
     http://127.0.0.1:5000/google_callback

Clique em "Criar"


Baixe o arquivo JSON das credenciais

4.4 Salvar o arquivo de credenciais

Renomeie o arquivo baixado para: client_secret.json
Coloque este arquivo na raiz do projeto (mesma pasta do run.py)


📧 Passo 5: Configurar o Envio de E-mails (Brevo)
5.1 Criar conta no Brevo (SendinBlue)

Acesse: https://www.brevo.com/
Crie uma conta gratuita
Confirme seu e-mail

5.2 Obter a chave API

Faça login no Brevo
Vá em "Configurações" (ícone de engrenagem) → "Chaves SMTP e API"
Na seção "Chaves API", clique em "Criar uma nova chave API"
Nomeie a chave (ex: "Sistema de Análise") e copie o valor

5.3 Anotar a chave API
Guarde esta chave, você precisará dela no arquivo .env

🤖 Passo 6: Configurar a IA Gemini (Google)
6.1 Acessar o Google AI Studio

Acesse: https://aistudio.google.com/
Faça login com sua conta Google
Clique em "Get API Key"
Selecione seu projeto do Google Cloud (criado no Passo 4)
Clique em "Create API Key"

6.2 Copiar a chave API
Copie a chave gerada - será usada no arquivo .env

⚙️ Passo 7: Criar o Arquivo .env
7.1 Criar o arquivo
Na raiz do projeto, crie um arquivo chamado .env (sem extensão, apenas ".env")
7.2 Preencher as variáveis
Cole o seguinte conteúdo e substitua os valores pelas suas credenciais:
env# Chave secreta do Flask (gere uma aleatória)
SECRET_KEY=sua_chave_secreta_muito_segura_aqui_12345

# URL de conexão com o PostgreSQL
DATABASE_URL=postgresql://meu_usuario:minha_senha_segura@localhost:5432/meu_banco_dados

# Credenciais do Google OAuth (do arquivo client_secret.json)
GOOGLE_CLIENT_ID=seu_client_id_do_google.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu_client_secret_do_google

# Chave API do Brevo (para envio de e-mails)
BREVO_API_KEY=sua_chave_api_do_brevo

# Chave API do Google Gemini (IA)
GEMINI_API_KEY=sua_chave_api_do_gemini

# Chave secreta para webhooks (gere uma aleatória)
WEBHOOK_SECRET_KEY=chave_webhook_segura_123abc
7.3 Gerar chaves secretas seguras
Para gerar chaves aleatórias seguras, execute no terminal Python:
pythonpython -c "import secrets; print(secrets.token_hex(32))"
Use a saída para SECRET_KEY e WEBHOOK_SECRET_KEY

🗂️ Passo 8: Estrutura de Pastas
Certifique-se de que a estrutura do projeto está assim:
meu-projeto-analise/
│
├── venv/                    # Ambiente virtual (não commitar)
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── utils.py
│   ├── static/
│   │   └── css/
│   │       └── style.css
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── login.html
│       └── (outros templates...)
│
├── client_secret.json       # Credenciais Google (não commitar)
├── .env                     # Variáveis de ambiente (não commitar)
├── .gitignore
├── config.py
├── requirements.txt
├── run.py
├── reset_db.py
└── (outros arquivos...)

🎯 Passo 9: Inicializar o Banco de Dados
9.1 Criar as tabelas
Com o ambiente virtual ativo, execute:
bashpython run.py
Aguarde a mensagem de que as tabelas foram criadas. Pressione Ctrl+C para parar o servidor.
9.2 (Opcional) Resetar o banco
Se precisar limpar e recriar as tabelas:
bashpython reset_db.py

▶️ Passo 10: Executar o Sistema
10.1 Iniciar o servidor
bashpython run.py
Você verá algo como:
* Running on http://127.0.0.1:5000
* Debug mode: on
10.2 Acessar no navegador
Abra seu navegador e acesse: http://localhost:5000

✅ Passo 11: Testar a Conexão com o Google
11.1 Executar o teste
Antes de usar o sistema completo, teste a conexão:
bashpython test_google_api.py
11.2 Autorizar no navegador

Um navegador será aberto automaticamente
Faça login com sua conta Google
Autorize as permissões solicitadas
Aguarde a mensagem de sucesso no terminal

11.3 Verificar credenciais
Se o teste for bem-sucedido, um arquivo credencial_google.json será criado. Isso confirma que a integração está funcionando.

🔍 Passo 12: Verificar se Tudo Está Funcionando
12.1 Checklist de verificação
✅ Servidor Flask rodando sem erros
✅ Página de login acessível
✅ Consegue criar uma conta
✅ E-mail de confirmação chegou
✅ Conexão com Google funcionando
✅ Banco de dados salvando informações
12.2 Rota de saúde do sistema
Acesse: http://localhost:5000/health
Você verá um JSON mostrando o status de cada componente:
json{
  "status": "healthy",
  "database": "OK",
  "google_credentials": "OK",
  "webhook_secret": "Configurado",
  "email_config": "Configurado"
}

🛠️ Solução de Problemas Comuns
Erro: "ModuleNotFoundError"
Solução: Certifique-se de que o ambiente virtual está ativo e reinstale as dependências:
bashpip install -r requirements.txt
Erro: "No such file or directory: '.env'"
Solução: Crie o arquivo .env na raiz do projeto com todas as variáveis necessárias.
Erro: "FATAL: password authentication failed"
Solução: Verifique se o usuário e senha do PostgreSQL estão corretos na variável DATABASE_URL.
Erro ao conectar com Google
Solução:

Verifique se o client_secret.json está na raiz do projeto
Confirme que as URIs de redirecionamento estão configuradas no Google Cloud Console
Execute novamente o test_google_api.py

E-mails não estão sendo enviados
Solução:

Verifique se a chave API do Brevo está correta
Confirme que o e-mail remetente está verificado no Brevo
Teste a rota: http://localhost:5000/test_email (após login)


🔒 Segurança - Arquivos que NUNCA devem ser commitados
Certifique-se de que o .gitignore contém:
gitignore# Ambiente Virtual
venv/

# Arquivos de ambiente com segredos
.env

# Credenciais do Google
client_secret.json
credencial_google.json

# Arquivos compilados
__pycache__/
*.pyc

📚 Recursos Adicionais

Documentação Flask: https://flask.palletsprojects.com/
Documentação Google APIs: https://developers.google.com/sheets/api
Documentação Brevo: https://developers.brevo.com/
Documentação PostgreSQL: https://www.postgresql.org/docs/


🎓 Próximos Passos
Após a instalação bem-sucedida:

✅ Crie sua primeira conta no sistema
✅ Conecte sua conta Google
✅ Busque seus Google Forms
✅ Processe as respostas
✅ Explore as análises descritivas e de Machine Learning


💡 Dicas Importantes

Mantenha as chaves seguras: Nunca compartilhe seu arquivo .env ou client_secret.json
Backup regular: Faça backup do banco de dados periodicamente
Atualizações: Mantenha as dependências atualizadas com pip install --upgrade -r requirements.txt
Logs: Monitore os logs do terminal para identificar possíveis erros


🎉 Parabéns! Seu sistema está pronto para uso!Tentar novamenteClaude ainda não tem a capacidade de executar o código que gera.
