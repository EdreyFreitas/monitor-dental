import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import re
import time
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Monitor Dental Cloud", page_icon="🦷", layout="wide")

DB_FILE = "produtos.json"
HIST_FILE = "historico.json"

def carregar_json(arquivo):
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "r") as f: return json.load(f)
        except: return []
    return []

def salvar_json(arquivo, dados):
    with open(arquivo, "w") as f: json.dump(dados, f, indent=4)

# --- MOTOR DE SCRAPING ADAPTADO PARA NUVEM ---
def capturar_loja(tarefa):
    url = tarefa['url']
    seletor = tarefa['seletor']
    loja = tarefa['loja']
    
    if not url or url == "": return {"loja": loja, "valor": "N/A"}
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,720")
    # Bloqueia imagens para ser rápido
    prefs = {"profile.managed_default_content_settings.images": 2}
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    # Gerencia o Driver (Funciona no seu PC e na Nuvem)
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except:
        driver = webdriver.Chrome(options=opts)
    
    try:
        driver.get(url)
        # Espera o preço aparecer
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor)))
        time.sleep(2) # Pausa mínima para JS
        
        elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
        precos_encontrados = []
        
        for el in elementos:
            # Limpeza profunda para Surya e Vidafarma
            texto = el.text.replace(' ', '').replace('\xa0', '').replace('\n', '')
            matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
            for m in matches:
                val = float(m.replace('.', '').replace(',', '.'))
                if val > 0: precos_encontrados.append(val)
        
        preco_final = min(precos_encontrados) if precos_encontrados else 0.0
        
        # Estoque
        html = driver.page_source.lower()
        if "vidafarma" in url.lower():
            est = "✅" if "comprar" in html or "adicionar" in html else "❌"
        else:
            esgotado = any(t in html for t in ['esgotado', 'indisponível', 'avise-me', 'fora de estoque'])
            est = "❌" if esgotado else "✅"
            
        return {"loja": loja, "valor": f"R$ {preco_final:,.2f} {est}".replace('.',',')}
    except:
        return {"loja": loja, "valor": "Erro ❌"}
    finally:
        driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Painel", "➕ Configurações"])

with aba_config:
    st.subheader("Cadastro de Links")
    with st.form("add_form", clear_on_submit=True):
        nome = st.text_input("Nome do Produto")
        c1, c2 = st.columns(2)
        v = c1.text_input("Link Vidafarma")
        cr = c2.text_input("Link Cremer")
        sp = c1.text_input("Link Speed")
        sy = c2.text_input("Link Surya")
        if st.form_submit_button("Salvar"):
            if nome and v:
                l = carregar_json(DB_FILE)
                l.append({"nome": nome, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
                salvar_json(DB_FILE, l)
                st.rerun()
    
    # Listagem para deletar
    prods = carregar_json(DB_FILE)
    for i, p in enumerate(prods):
        col1, col2 = st.columns([5,1])
        col1.write(f"📦 {p['nome']}")
        if col2.button("Remover", key=f"del_{i}"):
            prods.pop(i)
            salvar_json(DB_FILE, prods)
            st.rerun()

with aba_dash:
    historico = carregar_json(HIST_FILE)
    
    if st.button("🚀 ATUALIZAR PREÇOS AGORA"):
        lista_prods = carregar_json(DB_FILE)
        if not lista_prods:
            st.error("Nenhum produto cadastrado.")
        else:
            # Cria lista de tarefas individuais para paralelismo total
            tarefas = []
            for p in lista_prods:
                tarefas.append({"id": p['nome'], "loja": "Vidafarma (MEU)", "url": p['vidafarma'], "seletor": ".customProduct__price"})
                tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
                tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
                tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

            with st.status("Robôs na nuvem trabalhando...", expanded=True):
                # Usamos 3 ou 4 workers para não sobrecarregar o servidor grátis
                with ThreadPoolExecutor(max_workers=3) as executor:
                    res_brutos = list(executor.map(capturar_loja, tarefas))
                
                # Organiza para tabela
                matriz = {}
                for i, t in enumerate(tarefas):
                    if t['id'] not in matriz: matriz[t['id']] = {"Produto": t['id']}
                    matriz[t['id']][t['loja']] = res_brutos[i]['valor']
                
                final_dados = list(matriz.values())
                salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": final_dados}])
                st.rerun()

    if historico:
        st.info(f"Última atualização: {historico[0]['data']}")
        df = pd.DataFrame(historico[0]['dados'])
        st.dataframe(df.set_index("Produto"), use_container_width=True)
    else:
        st.warning("Clique no botão acima para buscar os preços pela primeira vez.")
