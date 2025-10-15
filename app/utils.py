import os
import json
import re
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import google.generativeai as genai

# Cache em memória
column_mapping_cache = {}

def send_email(to_email, subject, html_content):
    """Envia e-mails usando a API da Brevo."""
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = os.environ.get('BREVO_API_KEY')
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    sender = {"name": "Meu App", "email": "willianteo@gmail.com"}
    to = [{"email": to_email}]
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=html_content, sender=sender, subject=subject)

    try:
        api_instance.send_transac_email(send_smtp_email)
        print("E-mail enviado com sucesso!")
    except ApiException as e:
        print(f"Erro ao enviar e-mail: {e}")


def fallback_column_mapping(header_row):
    """Mapeamento manual com busca por palavras-chave."""
    mapping = {'nome': None, 'idade': None, 'cidade': None, 'curso_interesse': None}
    patterns = {
        'nome': [r'nome', r'name'],
        'idade': [r'idade', r'age'],
        'cidade': [r'cidade', r'city'],
        'curso_interesse': [r'curso', r'interesse']
    }
    for field, pattern_list in patterns.items():
        for idx, header in enumerate(header_row):
            for pattern in pattern_list:
                if re.search(pattern, str(header).lower()):
                    mapping[field] = idx
                    break
            if mapping[field] is not None:
                break
    return mapping


def get_column_mapping_from_ai(header_row):
    """Mapeia colunas usando IA ou fallback."""
    header_key = tuple(header_row)
    if header_key in column_mapping_cache:
        return column_mapping_cache[header_key]

    try:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel('models/gemini-pro-latest')
        prompt = f"""Mapeie os cabeçalhos para o esquema: {json.dumps(header_row)}. Retorne APENAS JSON com as chaves 'nome', 'idade', 'cidade', 'curso_interesse' e seus índices correspondentes ou null."""
        response = model.generate_content(prompt)
        cleaned = re.sub(r'```json\s*|```\s*', '', response.text.strip())
        mapping = json.loads(cleaned)
        if mapping.get('nome') is None:
            raise ValueError("IA não encontrou a coluna 'nome'")
        column_mapping_cache[header_key] = mapping
        return mapping
    except Exception as e:
        print(f"Erro na IA, usando fallback: {e}")
        return fallback_column_mapping(header_row)


def gerar_insights_com_ia(dados):
    """Usa Gemini para gerar insights inteligentes sobre os dados dos estudantes."""
    try:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel('models/gemini-pro-latest')
        
        prompt = f"""Você é um especialista em análise de dados educacionais e marketing. Analise os seguintes dados e forneça insights acionáveis em formato JSON:

DADOS:
- Total de estudantes: {dados['total_estudantes']}
- Idade média geral: {dados['idade_media_geral']}
- Cursos mais populares: {json.dumps(dados['cursos_populares'], ensure_ascii=False)}
- Cidades principais: {json.dumps(dados['cidades_principais'], ensure_ascii=False)}
- Segmentos (K-Means): {json.dumps(dados['segmentos'], indent=2, ensure_ascii=False)}

TAREFA:
Retorne um JSON com as seguintes chaves:
1. "resumo_executivo": Um parágrafo destacando os principais achados.
2. "tendencias": Array com 3 tendências específicas (use números).
3. "recomendacoes": Array com 3 ações estratégicas recomendadas.
4. "previsoes": String com uma previsão de demanda futura.
5. "segmento_destaque": String explicando qual perfil tem maior potencial.

REGRAS:
- Responda APENAS com JSON válido.
- Seja profissional e acionável.
"""
        response = model.generate_content(prompt)
        cleaned = re.sub(r'```json\s*|```\s*', '', response.text.strip())
        insights = json.loads(cleaned)
        
        required_keys = ['resumo_executivo', 'tendencias', 'recomendacoes', 'previsoes', 'segmento_destaque']
        if not all(key in insights for key in required_keys):
            raise ValueError("JSON incompleto da IA")
        
        print("✅ Insights gerados com sucesso pela IA")
        return insights
        
    except Exception as e:
        print(f"❌ Erro ao gerar insights com IA: {e}")
        return gerar_insights_fallback(dados)


def gerar_insights_fallback(dados):
    """Gera insights básicos quando a IA não está disponível."""
    total = dados.get('total_estudantes', 0)
    idade_media = dados.get('idade_media_geral', 0)
    curso_top = max(dados.get('cursos_populares', {}).items(), key=lambda x: x[1], default=("N/A", 0))
    cidade_top = max(dados.get('cidades_principais', {}).items(), key=lambda x: x[1], default=("N/A", 0))
    maior_segmento = max(dados.get('segmentos', []), key=lambda x: x.get('total_alunos', 0), default={'id': 0, 'total_alunos': 0})
    
    return {
        'resumo_executivo': f"Análise de {total} estudantes indica uma idade média de {idade_media} anos e forte interesse no curso de '{curso_top[0]}'.",
        'tendencias': [f"Concentração de interesse em '{curso_top[0]}'.", f"'{cidade_top[0]}' como polo geográfico principal.", f"Perfil {maior_segmento['id']} é o maior grupo, com {maior_segmento.get('total_alunos', 0)} estudantes."],
        'recomendacoes': ["Focar marketing na cidade principal.", "Expandir oferta de cursos similares ao mais popular.", "Criar campanhas para o maior segmento."],
        'previsoes': "A demanda pelo curso principal deve continuar alta.",
        'segmento_destaque': f"O Perfil {maior_segmento['id']} tem maior potencial por ser o maior grupo."
    }


def preparar_dados_graficos(df, segmentos):
    """Prepara dados formatados para visualizações JavaScript/Chart.js."""
    cores_segmentos = ['#0049ac', '#fb1515', '#282e47', '#6c757d']
    
    timeline_data = df.groupby(df['timestamp_cadastro'].dt.date).size()
    
    return {
        'distribuicao_segmentos': {
            'labels': [f"Perfil {s['id']+1}" for s in segmentos],
            'values': [s['total'] for s in segmentos],
            'cores': cores_segmentos[:len(segmentos)]
        },
        'idade_por_segmento': {
            'labels': [f"Perfil {s['id']+1}" for s in segmentos],
            'values': [s['idade_media'] for s in segmentos]
        },
        'timeline_cadastros': {
            'labels': timeline_data.index.astype(str).tolist()[-7:],
            'values': timeline_data.values.tolist()[-7:]
        }
    }