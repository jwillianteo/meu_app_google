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
    mapping = {
        'nome': None,
        'idade': None,
        'cidade': None,
        'curso_interesse': None
    }
    
    normalized_headers = [str(h).lower().strip() for h in header_row]
    
    # Padrões flexíveis
    patterns = {
        'nome': [r'nome', r'name'],
        'idade': [r'idade', r'age', r'anos'],
        'cidade': [r'cidade', r'city', r'onde mora'],
        'curso_interesse': [r'curso', r'course', r'interesse', r'área', r'animais', r'pet']  # ADICIONADO "animais"
    }
    
    for field, pattern_list in patterns.items():
        for idx, header in enumerate(normalized_headers):
            for pattern in pattern_list:
                if re.search(pattern, header):
                    mapping[field] = idx
                    print(f"✓ '{field}' → coluna {idx} ('{header_row[idx]}')")
                    break
            if mapping[field] is not None:
                break
    
    return mapping


def get_column_mapping_from_ai(header_row):
    """
    Mapeia colunas usando IA ou fallback, sendo FLEXÍVEL com o esquema.
    MODIFICADO: Aceita apenas 'nome' como obrigatório.
    """
    header_key = tuple(header_row)
    if header_key in column_mapping_cache:
        print("✓ Cache hit")
        return column_mapping_cache[header_key]

    print(f"\n📋 Cabeçalhos da planilha:")
    for idx, header in enumerate(header_row):
        print(f"  [{idx}] {header}")
    
    try:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel('models/gemini-pro-latest')

        prompt = f"""Mapeie os cabeçalhos para o esquema. Seja FLEXÍVEL.

CABEÇALHOS:
{chr(10).join([f'[{i}] {h}' for i, h in enumerate(header_row)])}

ESQUEMA (use null se não houver):
- nome: Nome da pessoa
- idade: Idade/anos
- cidade: Cidade/localização  
- curso_interesse: Curso, área de interesse, OU qualquer pergunta principal do formulário (animais, hobby, etc)

REGRAS:
1. Para 'curso_interesse', aceite QUALQUER pergunta relevante como: "animais", "hobby", "preferência"
2. Use o ÍNDICE numérico [0, 1, 2...]
3. Retorne APENAS JSON válido

EXEMPLO: {{"nome": 3, "idade": 4, "cidade": null, "curso_interesse": 2}}

Mapeie agora:"""

        print("🤖 Consultando IA...")
        response = model.generate_content(prompt)
        
        cleaned = re.sub(r'```json\s*|```\s*', '', response.text.strip())
        print(f"IA respondeu: {cleaned}")
        
        mapping = json.loads(cleaned)
        
        # VALIDAÇÃO MAIS FLEXÍVEL: apenas 'nome' é obrigatório
        if mapping.get('nome') is None:
            print("⚠️ IA não encontrou 'nome'. Tentando fallback...")
            mapping = fallback_column_mapping(header_row)
        
        # Se 'curso_interesse' estiver null mas existe uma coluna útil, use-a
        if mapping.get('curso_interesse') is None:
            # Tenta usar a primeira pergunta não-sistema (ignora timestamp, pontuação)
            for idx, header in enumerate(header_row):
                h_lower = header.lower()
                if idx > 1 and 'carimbo' not in h_lower and 'pontuação' not in h_lower and 'nome' not in h_lower and 'idade' not in h_lower:
                    mapping['curso_interesse'] = idx
                    print(f"🔄 Auto-selecionado 'curso_interesse' → coluna {idx} ('{header}')")
                    break
        
        # Validação final: apenas 'nome' é essencial
        if mapping.get('nome') is None:
            print("❌ Campo 'nome' não encontrado")
            return None
        
        print(f"✅ Mapeamento: {mapping}")
        column_mapping_cache[header_key] = mapping
        return mapping
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        mapping = fallback_column_mapping(header_row)
        
        # Auto-seleciona curso_interesse se não encontrado
        if mapping.get('curso_interesse') is None and mapping.get('nome') is not None:
            for idx, header in enumerate(header_row):
                h_lower = header.lower()
                if idx > 1 and 'carimbo' not in h_lower and 'pontuação' not in h_lower:
                    mapping['curso_interesse'] = idx
                    break
        
        if mapping.get('nome') is not None:
            column_mapping_cache[header_key] = mapping
            return mapping
        return None