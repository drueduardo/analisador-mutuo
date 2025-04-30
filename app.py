import streamlit as st
import pdfplumber
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO
import re

st.set_page_config(page_title="Analisador de Mútuos", layout="wide")

PALAVRAS_CHAVE = ["mútuo", "mútuos", "empréstimo entre partes relacionadas"]
REGEX_VALORES = re.compile(r"R?\$?\s?[\d\.]+(?:,\d+)?", re.IGNORECASE)
PALAVRAS_RELEVANTES_PDF = ["ITR", "Demonstrações Financeiras", "Balanço", "Relatório de Resultados", "Relatório Financeiro"]

st.title("🔍 Analisador de Mútuos em PDFs Financeiros")

def analisar_pdf(file, nome_arquivo):
    resultados = []
    with pdfplumber.open(file) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            if not texto:
                st.warning(f"Sem texto extraído da página {i} do arquivo {nome_arquivo}.")
                continue

            # Exibir o conteúdo extraído para depuração
            st.write(f"Conteúdo extraído da página {i} de {nome_arquivo}:", texto)

            # Normalizar o texto para evitar problemas com quebras de linha ou espaços extras
            texto = ' '.join(texto.split())
            texto_linhas = texto.lower().split("\n")

            # Ajustar a busca das palavras-chave
            for linha in texto_linhas:
                if any(palavra in linha for palavra in PALAVRAS_CHAVE):
                    valores = REGEX_VALORES.findall(linha)
                    resultados.append({
                        "Arquivo": nome_arquivo,
                        "Página": i,
                        "Tipo": "Texto",
                        "Conteúdo": linha.strip(),
                        "Valores": ", ".join(valores) if valores else "Não encontrado"
                    })

            # Verificar se a página contém tabelas e buscar palavras-chave
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    if linha and any(cell and any(palavra in cell.lower() for palavra in PALAVRAS_CHAVE) for cell in linha):
                        valores = [cell for cell in linha if cell and REGEX_VALORES.search(cell)]
                        resultados.append({
                            "Arquivo": nome_arquivo,
                            "Página": i,
                            "Tipo": "Tabela",
                            "Conteúdo": " | ".join(cell.strip() if cell else "" for cell in linha),
                            "Valores": ", ".join(valores) if valores else "Não encontrado"
                        })
    return resultados

aba = st.sidebar.radio("Escolha o modo de uso:", ["🌐 Scraping de página RI", "📁 Upload de PDFs"])

def exibir_resultados(resultados):
    if resultados:
        df = pd.DataFrame(resultados)
        st.success(f"{len(df)} ocorrências encontradas.")
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇️ Baixar como Excel", df.to_excel(index=False), file_name="resultados_mutuos.xlsx")
    else:
        st.warning("Nenhuma ocorrência encontrada.")

if aba == "🌐 Scraping de página RI":
    url = st.text_input("Cole a URL da página de RI da empresa (onde estão os PDFs):", "https://ri.portoseguro.com.br/informacoes-aos-acionistas/demonstracoes-financeiras-por-empresa/")
    if url and st.button("🔎 Buscar PDFs e analisar"):
        with st.spinner("Buscando PDFs..."):
            try:
                res = requests.get(url)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # Procurar por links de PDFs com palavras-chave relevantes
                links = [a['href'] for a in soup.find_all('a', href=True) if ".pdf" in a['href']]
                links = [l if l.startswith("http") else requests.compat.urljoin(url, l) for l in links]
                
                # Filtrar links para apenas aqueles que contêm palavras-chave no link ou na descrição
                links_relevantes = []
                for link in links:
                    if any(palavra in link for palavra in PALAVRAS_RELEVANTES_PDF):
                        links_relevantes.append(link)
                
                if not links_relevantes:
                    st.warning("Nenhum link relevante para PDF encontrado na página.")
                
                todos_resultados = []
                for link in links_relevantes:
                    nome_arquivo = link.split("/")[-1].split("?")[0]
                    try:
                        pdf_content = requests.get(link).content
                        resultados = analisar_pdf(BytesIO(pdf_content), nome_arquivo)
                        todos_resultados.extend(resultados)
                    except Exception as e:
                        st.warning(f"Erro ao processar: {nome_arquivo}")
                exibir_resultados(todos_resultados)
            except Exception as e:
                st.error(f"Erro ao acessar a página: {e}")

elif aba == "📁 Upload de PDFs":
    arquivos = st.file_uploader("Faça upload de um ou mais PDFs", type="pdf", accept_multiple_files=True)
    if arquivos:
        todos_resultados = []
        for file in arquivos:
            resultados = analisar_pdf(BytesIO(file.read()), file.name)
            todos_resultados.extend(resultados)
        exibir_resultados(todos_resultados)
