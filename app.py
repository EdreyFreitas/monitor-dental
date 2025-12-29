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
st.set_page_config(page_title="Monitor Dental Curva A", page_icon="🦷", layout="wide")

# ==========================================================
# 🟢 SUA CURVA A (COLOQUE SEUS PRODUTOS FIXOS AQUI)
# Estes produtos NUNCA serão apagados no reboot
# ==========================================================
PRODUTOS_FIXOS = [
    {
        "nome": "Resina Z100 3M - CURVA A",
        "vidafarma": "https://dentalvidafarma.com.br/resina-z100-3m-solventum",
        "cremer": "https://www.dentalcremer.com.br/resina-z100tm-3m-solventum-dc10933.html",
        "speed": "https://www.dentalspeed.com/resina-z100-3m-solventum-3369.html",
        "surya": "https://www.suryadental.com.br/resina-z100-4g-3m.html"
    },
    # Para adicionar mais, basta copiar o bloco acima e colar aqui embaixo:
]
# ==========================================================

DB_FILE = "produtos_extras.json"
HIST_FILE = "historico.json"

def carregar_json(arquivo):
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "r") as f: return json.load(f)
        except: return []
    return []

def salvar_json(arquivo, dados):
    with open(arquivo, "w") as f: json.dump(dados, f, indent=4)

def capturar_loja(tarefa):
    url = tarefa['url']
    seletor = tarefa['seletor']
    loja = tarefa['loja']
    if not url or url == "" or url == "N/A": return {"loja": loja, "valor": "N/A"}
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,720")
    prefs = {"profile.managed_default_content_settings.images": 2}
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except:
        driver = webdriver.Chrome(options=opts)
    
    try:
        driver.get(url)
        tempo_espera = 20 if "surya" in url.lower() else 15
        
        # Seletor inteligente para Surya
        css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor

        WebDriverWait(driver, tempo_espera).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
        time.sleep(3)
        
        elementos = driver.find_elements(By.CSS_SELECTOR, css)
        precos = []
        for el in elementos:
            t = el.text.replace(' ', '').replace('\xa0', '').replace('\n', '')
            m = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', t)
            precos.extend([float(v.replace('.', '').replace(',', '.')) for v in m])
        
        p_final = min(precos) if precos else 0.0
        html = driver.page_source.lower()
        if "vidafarma" in url.lower():
            est = "✅" if "comprar" in html or "adicionar" in html else "❌"
        else:
            esg = any(t in html for t in ['esgotado', 'indisponível', 'avise', 'fora de estoque'])
            est = "❌" if esg else "✅"
            
        return {"loja": loja, "valor": f"R$ {p_final:,.2f} {est}".replace('.',',')}
    except:
        return {"loja": loja, "valor": "Erro ❌"}
    finally:
        driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Painel de Controle", "⚙️ Gerenciar Extras"])

with aba_config:
    st.subheader("Produtos Extras (Temporários)")
    st.info("A Curva A já está fixa no sistema. Use este campo para testes ou promoções rápidas.")
    with st.form("add_form", clear_on_submit=True):
        nome = st.text_input("Nome do Produto Extra")
        c1, c2 = st.columns(2)
        v = c1.text_input("Link Vidafarma")
        cr = c2.text_input("Link Cremer")
        sp = c1.text_input("Link Speed")
        sy = c2.text_input("Link Surya")
        if st.form_submit_button("Adicionar"):
            if nome and v:
                extras = carregar_json(DB_FILE)
                extras.append({"nome": nome, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
                salvar_json(DB_FILE, extras)
                st.rerun()
    
    extras = carregar_json(DB_FILE)
    for i, p in enumerate(extras):
        col1, col2 = st.columns([5,1])
        col1.write(f"📦 {p['nome']}")
        if col2.button("Remover", key=f"del_{i}"):
            extras.pop(i)
            salvar_json(DB_FILE, extras)
            st.rerun()

with aba_dash:
    historico = carregar_json(HIST_FILE)
    
    if st.button("🚀 ATUALIZAR TODOS OS PREÇOS"):
        # Combina Curva A fixa com os Extras do JSON
        todos_produtos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        
        if not todos_produtos:
            st.error("Nenhum produto encontrado!")
        else:
            tarefas = []
            for p in todos_produtos:
                tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
                tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
                tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
                tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

            with st.status("Varredura em andamento...", expanded=True):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    res_brutos = list(executor.map(capturar_loja, tarefas))
                
                matriz = {}
                for i, t in enumerate(tarefas):
                    p_id = t['id']
                    if p_id not in matriz: matriz[p_id] = {"Produto": p_id}
                    matriz[p_id][t['loja']] = res_brutos[i]['valor']
                
                final_dados = list(matriz.values())
                salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": final_dados}])
                st.rerun()

    if historico:
        df = pd.DataFrame(historico[0]['dados'])
        
        # --- CÁLCULOS DASHBOARD ---
        def extrair_v(texto):
            try:
                num = re.search(r'R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', str(texto))
                return float(num.group(1).replace('.', '').replace(',', '.')) if num else None
            except: return None

        total = len(df)
        ganhando, perdendo, ruptura = 0, 0, 0
        for _, row in df.iterrows():
            meu_p = extrair_v(row['Vidafarma'])
            if "❌" in str(row['Vidafarma']): ruptura += 1
            concs = [extrair_v(row[c]) for c in ['Cremer', 'Speed', 'Surya'] if extrair_v(row[c])]
            if meu_p and concs:
                if meu_p < min(concs): ganhando += 1
                elif meu_p > min(concs): perdendo += 1

        p_ganh = (ganhando / total) * 100 if total > 0 else 0
        p_perd = (perdendo / total) * 100 if total > 0 else 0
        p_rupt = (ruptura / total) * 100 if total > 0 else 0

        # --- BARRAS DE PERFORMANCE ---
        def criar_barra(label, percent, cor):
            st.markdown(f"""
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-weight: bold; font-size: 14px;">{label}</span>
                        <span style="font-weight: bold; font-size: 14px;">{percent:.1f}%</span>
                    </div>
                    <div style="background-color: #e0e0e0; border-radius: 10px; width: 100%; height: 18px;">
                        <div style="background-color: {cor}; width: {percent}%; height: 100%; border-radius: 10px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1: criar_barra("🔥 Ganhando", p_ganh, "#28a745")
        with col2: criar_barra("⚠️ Perdendo", p_perd, "#dc3545")
        with col3: criar_barra("📦 Sua Ruptura", p_rupt, "#6c757d")

        st.divider()
        st.info(f"Relatório de {historico[0]['data']}")
        st.dataframe(df.set_index("Produto"), use_container_width=True)
    else:
        st.warning("Clique em 'Atualizar' para ver os preços da Curva A.")
