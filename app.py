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

# CSS PREMIUM (UI/UX SaaS)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .stButton>button {
        background: linear-gradient(90deg, #007BFF 0%, #0056b3 100%);
        color: white; border: none; border-radius: 8px; padding: 0.6rem 2rem;
        font-weight: 700; width: 100%; transition: 0.3s;
    }
    
    .kpi-container {
        background: #1e1e1e; padding: 20px; border-radius: 12px;
        border: 1px solid #333; margin-bottom: 20px;
    }

    .product-header {
        background: #252525; padding: 10px 20px; border-radius: 8px 8px 0 0;
        border-left: 5px solid #007BFF; margin-top: 20px;
    }

    .shop-card {
        background: #181818; border: 1px solid #333; border-radius: 12px;
        padding: 20px; text-align: center; height: 100%;
        transition: all 0.3s ease;
    }
    
    .shop-card:hover { border-color: #007BFF; transform: translateY(-3px); }

    .price-large {
        font-size: 24px; font-weight: 700; color: #fff; margin: 10px 0;
    }

    .shop-title { color: #888; font-size: 12px; text-transform: uppercase; font-weight: 600; }
    
    .badge {
        padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;
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
    if not url or len(url) < 10: return {"loja": loja, "valor": 0.0, "estoque": "N/A", "url": url}
    
    driver = None
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # Inicialização do Driver com tratamento para Streamlit Cloud
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        
        driver.get(url)
        # Espera extra para sites pesados
        wait_time = 25 if "surya" in url.lower() else 15
        target_css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        
        WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, target_css)))
        time.sleep(5) # Delay necessário para carregar preços dinâmicos
        
        elemento = driver.find_element(By.CSS_SELECTOR, target_css)
        texto = elemento.text.replace('\xa0', ' ').replace('\n', ' ')
        
        # Extração de Preços
        matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        precos = [float(m.replace('.', '').replace(',', '.')) for m in matches]
        
        if not precos: return {"loja": loja, "valor": 0.0, "estoque": "Sem Preço", "url": url}

        if "vidafarma" in url.lower():
            preco_final = max(precos) # Pega o valor cheio (não parcelado)
        else:
            preco_final = min(precos) # Pega o valor à vista
            
        html = driver.page_source.lower()
        if "vidafarma" in url.lower():
            est = "✅ Disponível" if "comprar" in html or "adicionar" in html else "❌ Esgotado"
        else:
            esg = any(t in html for t in ['esgotado', 'indisponível', 'avise', 'fora de estoque'])
            est = "❌ Esgotado" if esg else "✅ Disponível"
            
        return {"loja": loja, "valor": preco_final, "estoque": est, "url": url}
    except Exception as e:
        return {"loja": loja, "valor": 0.0, "estoque": f"Erro", "url": url}
    finally:
        if driver: driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Market Overview", "⚙️ Configuração"])

with aba_config:
    st.subheader("Cadastro de Novos Links")
    with st.form("form_add", clear_on_submit=True):
        nome = st.text_input("Nome do Produto")
        c1, c2 = st.columns(2)
        v = c1.text_input("Link Vidafarma")
        cr = c2.text_input("Link Cremer")
        sp = c1.text_input("Link Speed")
        sy = c2.text_input("Link Surya")
        if st.form_submit_button("Salvar na Base"):
            if nome and v:
                ex = carregar_json(DB_FILE); ex.append({"nome": nome, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
                salvar_json(DB_FILE, ex); st.rerun()

with aba_dash:
    hist = carregar_json(HIST_FILE)
    
    col_head, col_btn = st.columns([3, 1])
    with col_head:
        st.write("## 🏛️ Central de Inteligência")
    with col_btn:
        if st.button("🔄 ATUALIZAR MERCADO"):
            todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
            tarefas = []
            for p in todos:
                tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
                tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
                tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
                tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

            with st.status("Robôs sincronizando preços...", expanded=True):
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
            if "❌" in p['lojas']['Vidafarma']['estoque']: ruptura += 1
            
            outros = [v['valor'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['valor'] > 1.0]
            if meu_v > 1.0 and outros:
                menor_conc = min(outros)
                if meu_v < menor_conc: ganhando += 1
                elif abs(meu_v - menor_conc) < 0.05: empatados += 1
                else: perdendo += 1

        total = len(dados)
        st.markdown(f"#### 📊 Performance Geral (Base: {total} produtos)")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🟢 Ganhando", f"{(ganhando/total)*100:.1f}%")
        k2.metric("🤝 Empatados", f"{(empatados/total)*100:.1f}%")
        k3.metric("🔴 Perdendo", f"{(perdendo/total)*100:.1f}%")
        k4.metric("⚪ Sua Ruptura", f"{(ruptura/total)*100:.1f}%")
        st.caption(f"Última atualização: {hist[0]['data']}")
        st.divider()

        # --- CARDS SaaS ---
        for p in dados:
            st.markdown(f'<div class="product-header">{p["Produto"]}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for i, (loja, info) in enumerate(p['lojas'].items()):
                with cols[i]:
                    cor_borda = "#007BFF" if loja == "Vidafarma" else "#333"
                    preco_f = f"R$ {info['valor']:,.2f}".replace('.',',') if info['valor'] > 0 else "---"
                    status_cor = "green" if "✅" in info['estoque'] else "red"
                    
                    st.markdown(f"""
                    <div class="shop-card" style="border-top: 4px solid {cor_borda};">
                        <div class="shop-title">{loja}</div>
                        <div class="price-large">{preco_f}</div>
                        <div style="margin: 10px 0;">
                            <span class="badge" style="background: {status_cor}; color: white;">{info['estoque']}</span>
                        </div>
                        <a href="{info['url']}" target="_blank" style="text-decoration:none; font-size:14px;">Acessar Link ↗️</a>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
