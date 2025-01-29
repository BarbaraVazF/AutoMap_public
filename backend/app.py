from flask import Flask, request, jsonify
from flask_cors import CORS
import re
from difflib import SequenceMatcher
import openai
import json
from datetime import datetime
import pandas as pd
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import os

app = Flask(__name__)
CORS(app)  # Permite o CORS para comunicação com o front-end

@app.route('/upload', methods=['POST'])
def upload_files():

    load_dotenv()
    API_KEY = os.getenv("API_KEY")
    
    openai.api_key = API_KEY

    if 'pdf' not in request.files or 'csv' not in request.files:
        return jsonify({'error': 'Ambos os arquivos devem ser enviados (PDF e CSV).'}), 400

    # Recebe os arquivos
    pdf_file = request.files['pdf']
    csv_file = request.files['csv']

    # Obter informações dos arquivos
    #pdf_name = pdf_file.filename
    csv_name = csv_file.filename

    # Ler conteúdo do PDF (assumimos que é texto simples)
    try:
        pdf_content = ""
        leitor = PdfReader(pdf_file)
        for pagina in leitor.pages:
            pdf_content += pagina.extract_text()
    except UnicodeDecodeError as e:
        return jsonify({'error': 'Erro ao ler o conteúdo do arquivo PDF.'}), 400
    
    # Ler conteúdo do CSV
    try:
        #csv_content = csv_file.read().decode('utf-8')  # Usando utf-8 para CSV
        csv_content = pd.read_csv(csv_file, delimiter=';')
        primeira_linha = csv_content.iloc[0].to_dict()
        csv_content = {campo: str(valor) for campo, valor in primeira_linha.items()}
    except UnicodeDecodeError as e:
        return jsonify({'error': 'Erro ao ler o conteúdo do arquivo CSV.'}), 400
    
    
    def extrair_secoes_relevantes(pdf_content):
        try:
            padrao_secao = re.compile(r"(\d+\.\d+)\s+(Upload|Download)\s+-\s+(.+)")
            #fazer padrao secao 2 sem numero na frente
            secoes = []

            matches = list(padrao_secao.finditer(pdf_content))
            for i, match in enumerate(matches):
                numero_secao, tipo, nome_arquivo = match.groups()
                inicio = match.end()

                # Determinar o fim com base no próximo título, ou até o final do texto
                fim = matches[i + 1].start() if i + 1 < len(matches) else len(pdf_content)

                conteudo_secao = pdf_content[inicio:fim].strip()
                secoes.append({
                    "numero_secao": numero_secao,
                    "tipo": tipo,
                    "nome_arquivo": nome_arquivo.strip(),
                    "conteudo": conteudo_secao
                })

            return secoes
        except Exception as e:
            raise ValueError(f"Erro ao extrair seções do PDF: {e}")

    def calcular_similaridade(csv_name, nome_secao):
        return SequenceMatcher(None, csv_name.lower(), nome_secao.lower()).ratio()
    
    def selecionar_secao_por_similaridade(csv_name, pdf_content):
        secoes = extrair_secoes_relevantes(pdf_content)
        melhor_secao = None
        maior_similaridade = 0
        print(f"nome do csv: {csv_name}")
        for secao in secoes:
            similaridade = calcular_similaridade(csv_name[:-4], secao["nome_arquivo"])
            print(secao["nome_arquivo"])
            if similaridade > maior_similaridade:
                maior_similaridade = similaridade
                melhor_secao = secao

        if maior_similaridade >= 0.5:
            return melhor_secao['conteudo']
        else:
            raise ValueError("Nenhuma seção do PDF corresponde ao nome do arquivo CSV com similaridade >= 50%.")

    def extrair_campos_via_openai(texto_pdf):
        prompt = f"""
        O texto abaixo contém uma tabela com campos, tipos, tamanhos e complementos extraídos de um documento técnico. 
        Extraia os campos no formato JSON, com o nome do campo como chave e o tipo, tamanho e complemento como valor.
        Lembre-se que a lista de opções pode ser vazia
        Texto:
        {texto_pdf}

        Saída esperada:
        {{
            "nome_do_campo_1": "TIPO (tamanho) complemento",
            "nome_do_campo_2": "TIPO (tamanho) complemento",
            ...
        }}
        """
        try:
            resposta = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "Você é um assistente que transforma texto em JSON estruturado."},
                        {"role": "user", "content": prompt}],
                temperature=0
            )
            conteudo = resposta['choices'][0]['message']['content']
            # Validar se a resposta é um JSON
            try:
                return json.loads(conteudo)  # Verifica se a string é um JSON válido
            except json.JSONDecodeError:
                raise ValueError(f"A resposta da API não é um JSON válido: {conteudo}")
        except Exception as e:
            raise ValueError(f"Erro ao processar o texto via OpenAI: {e}")
        
    # ESTAVA FUNCIONANDO ATÉ AQUI!!!
        
    def validar_formato_data(campo, valor):
        try:
            datetime.strptime(valor, "%Y%m%d")
            return "data válida"
        except ValueError:
            return f"O campo {campo} deve estar no formato AAAAMMDD."
    
    def validar_tipo_tamanho(campo, valor, tamanho, tipo):
        valor = str(valor).strip()  # Remover espaços em branco ao redor

        if len(valor) == 0:
            return f"O campo {campo} deve ser diferente de nulo."

        if tipo == 'VARCHAR':
            if len(valor) > int(tamanho):
                return f"Tipo ok, mas o campo {campo} deve ter até {tamanho} caracteres."
            else:
                return "Tipo e quantidade ok"
        
        elif tipo == 'DECIMAL':
            valor = valor.replace(",", ".")
            try:
                # Verificar se é um número válido (inteiro ou decimal)
                valor = float(valor)
                partes = str(valor).split(".")

                # Validar partes inteira e decimal separadamente
                parte_inteira = len(partes[0].replace("-", ""))
                parte_decimal = len(partes[1]) if len(partes) > 1 else 0
                
                lista_tamanho = tamanho.split(",")

                max_inteiro = int(lista_tamanho[0]) - parte_decimal
                max_decimal = int(lista_tamanho[1])

                if parte_inteira > max_inteiro or parte_decimal > max_decimal:
                    return (
                        f"Tipo ok, mas o campo {campo} deve ter até {int(lista_tamanho[0])} caracteres, "
                        f"sendo até {max_inteiro} na parte inteira caso tenham {max_decimal} caracteres na parte decimal."
                    )
                else:
                    return "Tipo e quantidade ok"
            except:
                return f"O campo {campo} precisa ser um número decimal válido."

        return f"Tipo desconhecido para o campo {campo}."

    def validar_opcoes(campo, valor, opcoes):
        valor_normalizado = valor.replace(" ", "").upper()
        lista_opcoes = re.split(r",|\sou\s", opcoes)  # Divide as opções por vírgula ou "ou"
        lista_opcoes_normalizadas = [opcao.strip().replace(" ", "").upper() for opcao in lista_opcoes]

        if valor_normalizado in lista_opcoes_normalizadas:
            return "válido"
        else:
            return f"O campo {campo} precisa estar entre as opções {opcoes}."
        
    def comparar_listas(lista_PDF, lista_CSV):
        campos_inexistentes = []
        campos_faltantes = lista_PDF.copy()

        lista_PDF_normalizada = [valor.upper().replace(" ", "") for valor in lista_PDF]
        lista_CSV_normalizada = [valor.upper().replace(" ", "") for valor in lista_CSV]

        for i, valor2 in enumerate(lista_CSV_normalizada):
            maiores_similitudes = [(valor1, SequenceMatcher(None, valor2, valor1).ratio()) for valor1 in lista_PDF_normalizada]
            maior_similaridade = max(maiores_similitudes, key=lambda x: x[1], default=(None, 0))

            if maior_similaridade[1] > 0.5:
                campo_original = lista_PDF[lista_PDF_normalizada.index(maior_similaridade[0])]
                lista_CSV[i] = campo_original
                campos_faltantes.remove(campo_original)
            else:
                campos_inexistentes.append(lista_CSV[i])
        print(campos_faltantes)
        return lista_CSV, campos_faltantes, campos_inexistentes
    
    def extrair_detalhes_regra(regra):
        try:
            inicio = regra.index("(")
            fim = regra.index(")")
            tipo = regra[:inicio].strip()
            tamanho = regra[inicio + 1:fim].strip()
            complemento = regra[fim + 1:].strip()
            return tipo, tamanho, complemento
        except ValueError:
            raise ValueError("Erro ao extrair detalhes da regra.")
        
    def chamar_regras(texto_PDF, texto_CSV):
        try:
            regras = json.loads(texto_PDF)
            campos_CSV = json.loads(texto_CSV)

            lista_PDF = list(regras.keys())
            lista_CSV = list(campos_CSV.keys())

            lista_CSV_ajustada, campos_faltantes, campos_inexistentes = comparar_listas(lista_PDF, lista_CSV)

            validacoes = {}
            for i, (campo_original, valor) in enumerate(campos_CSV.items()):
                if i >= len(lista_CSV_ajustada):
                    validacoes[campo_original] = {
                        "erro": f"Índice fora do alcance para o campo {campo_original}."
                    }
                    continue

                campo = lista_CSV_ajustada[i]

                if campo in regras:
                    regra = regras[campo]
                    tipo, tamanho, complemento = extrair_detalhes_regra(regra)

                    opcoes = ""
                    status_opcoes = "não aplicável"
                    if "Enviar Fixo" in complemento:
                        opcoes = complemento.split("Enviar Fixo", 1)[1].strip()
                        status_opcoes = validar_opcoes(campo, str(valor), opcoes)
                    elif "Enviar o tipo" in complemento:
                        opcoes = complemento.split("Enviar o tipo", 1)[1].strip()
                        status_opcoes = validar_opcoes(campo, str(valor), opcoes)

                    # Verificar a data para múltiplos campos
                    status_data = "não aplicável"
                    if "AAAAMMDD" in complemento:
                        status_data = validar_formato_data(campo, str(valor))

                    status_tipo_caracteres = validar_tipo_tamanho(campo, str(valor), tamanho, tipo)

                    validacoes[campo_original] = {
                        "tipo_caracter": status_tipo_caracteres,
                        "complemento": status_opcoes,
                        "data": status_data
                    }
                else:
                    validacoes[campo_original] = {
                        "erro": f"Campo '{campo}' não encontrado nas regras."
                    }

            return {
                "validacoes": validacoes,
                "campos_faltantes": campos_faltantes,
                "campos_inexistentes": campos_inexistentes
            }

        except Exception as e:
            return {"erro": str(e)}
        
    def gerar_resposta(resultado):
        try:
            prompt = f"""
            O resultado da validação de campos contém informações sobre campos válidos, erros, campos faltantes e inexistentes. 
            Formule uma resposta clara e fluida ao usuário com base no seguinte JSON:

            {json.dumps(resultado, indent=4, ensure_ascii=False)}

            Resposta esperada:
            - Informe se todos os campos estão corretos. Caso existam erros, descreva os problemas encontrados. 
                - Agrupe todos os problemas de cada campo em uma única mensagem, sem duplicações. 
                - Por exemplo, se um valor apresenta erros em quantidade de caracteres e no formato, ambos devem ser descritos juntos.
            - Os campos corretos devem ser listados ao final da resposta no seguinte modelo: "Os campos (...) estão dentro das regras." Liste-os apenas uma vez.
            - Destaque os campos ausentes no CSV. 
            - Inclua, ao final, uma recomendação para o usuário revisar o manual de integração e corrigir inconsistências.
            """

            resposta = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um assistente que explica resultados de validações de maneira clara e objetiva."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            return resposta['choices'][0]['message']['content']

        except Exception as e:
            return f"Erro ao gerar a resposta com IA: {e}"

    conteudo_melhor_secao = selecionar_secao_por_similaridade(csv_name, pdf_content)
    campos_pdf = extrair_campos_via_openai(conteudo_melhor_secao)
    campos_pdf_json = json.dumps(campos_pdf, indent=4, ensure_ascii=False)
    csv_content_json = json.dumps(csv_content, indent=4, ensure_ascii=False)
    resultado = chamar_regras(campos_pdf_json, csv_content_json)
    resposta = gerar_resposta(resultado)


    # Exibir informações no console (Para fins de depuração)
    print(f"Resultado:\n{resposta}")
    # print(f"CSV: {csv_name}")
    # print(f"Conteúdo do CSV:\n{csv_content}")

    # Retornar a resposta
    return jsonify({
        'backendResponse': resposta  # Renomeie 'message' para 'backendResponse'
    })

if __name__ == '__main__':
    app.run(debug=True)