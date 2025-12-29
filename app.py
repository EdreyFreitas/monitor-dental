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
st.set_page_config(page_title="Dental Intelligence v2.0", page_icon="📈", layout="wide")

# CSS CUSTOMIZADO PARA VISUAL SaaS
st.markdown("""
<style>
    .product-card {
        background-color: #1E1E1E;
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 25px;
        border: 1px solid #333;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .shop-box {
        background-color: #2D2D2D;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border: 1px solid #444;
    }
    .price-text {
        font-size: 20px;
        font-weight: bold;
        color: #FFFFFF;
        margin: 5px 0;
    }
    .shop-name {
        font-size: 12px;
        color: #AAAAAA;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .status-badge {
        padding: 4px 10px;
        border-radius: 5px;
        font-size: 12px;
        font-weight: bold;
    }
    .link-btn {
        text-decoration: none;
        color: #007BFF;
        font-size: 18px;
    }
</style>
""", unsafe_allow_html=True)

# --- PRODUTOS FIXOS ---
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
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,720")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.get(url)
        wait_time = 20 if "surya" in url.lower() else 15
        css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
        time.sleep(3)
        
        elemento = driver.find_element(By.CSS_SELECTOR, css)
        texto = elemento.text.replace('\xa0', ' ').replace('\n', ' ')
        
        # Filtro de Preço Melhorado (Evitar parcelas)
        matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        precos = [float(m.replace('.', '').replace(',', '.')) for m in matches]
        
        if "vidafarma" in url.lower():
            # Na Vidafarma, o preço total é SEMPRE o maior (para ignorar o "2x de...")
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
        return {"loja": loja, "valor": 0.0, "estoque": "❌", "url": url}
    finally:
        driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Dashboard Real-time", "⚙️ Configurações"])

with aba_config:
    st.subheader("Gerenciar Produtos Extras")
    with st.form("add_form", clear_on_submit=True):
        nome = st.text_input("Nome do Produto")
        c1, c2 = st.columns(2)
        v, cr = c1.text_input("Link Vida"), c2.text_input("Link Cremer")
        sp, sy = c1.text_input("Link Speed"), c2.text_input("Link Surya")
        if st.form_submit_button("Adicionar"):
            if nome and v:
                ex = carregar_json(DB_FILE); ex.append({"nome": nome, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
                salvar_json(DB_FILE, ex); st.rerun()

with aba_dash:
    hist = carregar_json(HIST_FILE)
    
    if st.button("🚀 SINCRONIZAR TODOS OS PREÇOS"):
        todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        tarefas = []
        for p in todos:
            tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
            tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
            tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
            tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

        with st.status("Varrendo mercado...", expanded=True):
            with ThreadPoolExecutor(max_workers=4) as executor:
                brutos = list(executor.map(capturar_loja, tarefas))
            
            res_organizado = {}
            for i, t in enumerate(tarefas):
                pid = t['id']
                if pid not in res_organizado: res_organizado[pid] = {"Produto": pid, "lojas": {}}
                res_organizado[pid]["lojas"][t['loja']] = brutos[i]
            
            salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": list(res_organizado.values())}])
            st.rerun()

    if hist:
        # --- CÁLCULOS KPI ---
        dados = hist[0]['dados']
        ganhando, perdendo, empatados, ruptura = 0, 0, 0, 0
        
        for p in dados:
            v_data = p['lojas']['Vidafarma']
            meu_p = v_data['valor']
            if v_data['estoque'] == "❌": ruptura += 1
            
            outros = [v['valor'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['valor'] > 0]
            if meu_p > 0 and outros:
                menor_conc = min(outros)
                if meu_p < menor_conc: ganhando += 1
                elif meu_p == menor_conc: empatados += 1
                else: perdendo += 1

        total = len(dados)
        st.subheader("🎯 Performance de Precificação")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🟢 Ganhando", f"{(ganhando/total)*100:.1f}%")
        k2.metric("🤝 Empatados", f"{(empatados/total)*100:.1f}%")
        k3.metric("🔴 Perdendo", f"{(perdendo/total)*100:.1f}%")
        k4.metric("⚪ Ruptura", f"{(ruptura/total)*100:.1f}%")
        st.divider()

        # --- CONSTRUÇÃO DOS CARDS ---
        for p in dados:
            with st.container():
                st.markdown(f"### {p['Produto']}")
                cols = st.columns(4)
                
                for i, (loja_nome, info) in enumerate(p['lojas'].items()):
                    with cols[i]:
                        # Definir cor do status
                        cor_borda = "#444"
                        if loja_nome == "Vidafarma":
                            cor_borda = "#007BFF"
                        
                        preco_display = f"R$ {info['valor']:,.2f}".replace('.',',') if info['valor'] > 0 else "---"
                        
                        st.markdown(f"""
                        <div class="shop-box" style="border-top: 4px solid {cor_borda};">
                            <div class="shop-name">{loja_nome}</div>
                            <div class="price-text">{preco_display}</div>
                            <div style="margin-top:10px;">
                                <span>{info['estoque']}</span> | 
                                <a href="{info['url']}" target="_blank" class="link-btn">🔗</a>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
