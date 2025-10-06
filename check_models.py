import google.generativeai as genai
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Erro: A variável GEMINI_API_KEY não foi encontrada no arquivo .env")
    else:
        genai.configure(api_key=api_key)

        print("--- Modelos disponíveis para sua chave de API ---")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
        print("-------------------------------------------------")
        print("\nCopie um dos nomes de modelo acima (ex: 'models/gemini-1.5-flash-latest') e cole no arquivo app/utils.py.")

except Exception as e:
    print(f"Ocorreu um erro ao buscar os modelos: {e}")