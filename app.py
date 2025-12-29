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
st.set_page_config(page_title="Dental Intelligence SaaS", page_icon="📈", layout="wide")

# CSS CUSTOMIZADO PARA DESIGN SaaS PROFISSIONAL
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .kpi-card {
        background: #1E1E1E;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #007BFF;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.2);
    }

    .product-card {
        background: #181818;
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 20px;
        border: 1px solid #333;
    }

    .shop-tile {
        background: #252525;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        border: 1px solid #444;
        transition: transform 0.2s;
    }
    
    .shop-tile:hover {
        transform: translateY(-5px);
        border-color: #007BFF;
    }

    .price-val {
        font-size: 22px;
        font-weight: 800;
        color: #FFFFFF;
        display: block;
        margin: 5px 0;
    }

    .shop-label {
        color: #888;
        font-size: 11px;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    .link-icon {
        color: #007BFF;
        text-decoration: none;
        font-size: 18px;
    }
</style>
""", unsafe_allow_html=True)

# --- PRODUTOS FIXOS (CURVA A) ---
PRODUTOS_FIXOS = [
    {
        "nome": "Resina Z100 3M - A1",
        "vidafarma": "https://dentalvidafarma.com.br/resina-z100-3m-solventum",
        "cremer": "https://www.dentalcremer.com.br/resina-z100tm-3m-solventum-dc10933.html",
        "speed": "https://www.dentalspeed.com/resina-z100-3m-solventum-3369.html",
        "surya": "https://www.suryadental.com.br/resina-z100-4g-3m.html"
    },
    {
        "nome": "Anestésico Articaína DFL",
        "vidafarma": "https://dentalvidafarma.com.br/anestesico-articaina-4-cv-1-100-000-dfl",
        "cremer": "https://www.dentalcremer.com.br/anest-articaine-1-100-000-c-50-dfl-361044.html",
        "speed": "https://www.dentalspeed.com/anestesico-articaine-1-100-000-dfl.html",
        "surya": "https://www.suryadental.com.br/anestesico-articaine-1-100-000-dfl.html"
    }
]

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
    url, seletor, loja = tarefa['url'], tarefa['seletor'], tarefa['loja']
    if not url: return {"loja": loja, "valor": 0.0, "estoque": "❌", "url": ""}
    
    driver = None # Inicializa como nulo para evitar erro no finally
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,720")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.get(url)
        wait_time = 25 if "surya" in url.lower() else 15
        
        # Seletor inteligente para Surya
        seletor_css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        
        WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor_css)))
        time.sleep(4)
        
        elemento = driver.find_element(By.CSS_SELECTOR, seletor_css)
        texto = elemento.text.replace('\xa0', ' ').replace('\n', ' ')
        
        # Captura de valores numéricos
        matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        precos = [float(m.replace('.', '').replace(',', '.')) for m in matches]
        
        if "vidafarma" in url.lower():
            # Na Vidafarma, pegamos o MAIOR valor para ignorar parcelas (ex: 224,90 vs 112,45)
            preco_final = max(precos) if precos else 0.0
        else:
            preco_final = min(precos) if precos else 0.0
            
        html = driver.page_source.lower()
        if "vidafarma" in url.lower():
            est = "✅" if "comprar" in html or "adicionar" in html else "❌"
        else:
            esg = any(t in html for t in ['esgotado', 'indisponível', 'avise', 'fora de estoque'])
            est = "❌" if esg else "✅"
            
        return {"loja": loja, "valor": preco_final, "estoque": est, "url": url}
    except:
        return {"loja": loja, "valor": 0.0, "estoque": "Erro", "url": url}
    finally:
        if driver:
            driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Market Insights", "⚙️ Configuração"])

with aba_config:
    st.subheader("Cadastro de Produtos Extras")
    with st.form("form_add", clear_on_submit=True):
        nome = st.text_input("Nome do Produto")
        c1, c2 = st.columns(2)
        v = c1.text_input("Link Vidafarma")
        cr = c2.text_input("Link Cremer")
        sp = c1.text_input("Link Speed")
        sy = c2.text_input("Link Surya")
        if st.form_submit_button("Salvar"):
            if nome and v:
                ex = carregar_json(DB_FILE); ex.append({"nome": nome, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
                salvar_json(DB_FILE, ex); st.rerun()

with aba_dash:
    hist = carregar_json(HIST_FILE)
    
    col_bt1, col_bt2 = st.columns([3, 1])
    if col_bt1.button("🔄 ATUALIZAR PREÇOS AGORA", use_container_width=True):
        todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        tarefas = []
        for p in todos:
            tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
            tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
            tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
            tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

        with st.status("Robôs analisando o mercado...", expanded=True):
            with ThreadPoolExecutor(max_workers=4) as executor:
                brutos = list(executor.map(capturar_loja, tarefas))
            
            res_org = {}
            for i, t in enumerate(tarefas):
                pid = t['id']
                if pid not in res_org: res_org[pid] = {"Produto": pid, "lojas": {}}
                res_org[pid]["lojas"][t['loja']] = brutos[i]
            
            salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": list(res_org.values())}])
            st.rerun()

    if hist:
        # --- CÁLCULOS KPI ---
        dados = hist[0]['dados']
        ganhando, perdendo, empatados, ruptura = 0, 0, 0, 0
        
        for p in dados:
            meu_v = p['lojas']['Vidafarma']['valor']
            if p['lojas']['Vidafarma']['estoque'] == "❌": ruptura += 1
            
            outros = [v['valor'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['valor'] > 0]
            if meu_v > 0 and outros:
                menor_conc = min(outros)
                if meu_v < menor_conc: ganhando += 1
                elif meu_v == menor_conc: empatados += 1
                else: perdendo += 1

        total = len(dados)
        st.write("### 📈 Visão Geral de Performance")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🟢 Ganhando", f"{(ganhando/total)*100:.1f}%")
        k2.metric("🤝 Empatados", f"{(empatados/total)*100:.1f}%")
        k3.metric("🔴 Perdendo", f"{(perdendo/total)*100:.1f}%")
        k4.metric("⚪ Sua Ruptura", f"{(ruptura/total)*100:.1f}%")
        st.divider()

        # --- CARDS SaaS ---
        for p in dados:
            st.markdown(f"#### {p['Produto']}")
            cols = st.columns(4)
            for i, (loja, info) in enumerate(p['lojas'].items()):
                with cols[i]:
                    status_cor = "#007BFF" if loja == "Vidafarma" else "#444"
                    preco_format = f"R$ {info['valor']:,.2f}".replace('.',',') if info['valor'] > 0 else "---"
                    
                    st.markdown(f"""
                    <div class="shop-tile" style="border-top: 4px solid {status_cor};">
                        <div class="shop-label">{loja}</div>
                        <div class="price-val">{preco_format}</div>
                        <div style="font-size: 13px; margin-top: 10px;">
                            {info['estoque']} | <a href="{info['url']}" target="_blank" class="link-icon">↗️</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.warning("Nenhum dado capturado. Clique em atualizar para carregar a Curva A.")
