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
import shutil
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dental Intelligence SaaS", page_icon="📈", layout="wide")

# UI SaaS PREMIUM
st.markdown("""
<style>
    .shop-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; text-align: center; margin-bottom: 10px;
    }
    .price-tag { font-size: 24px; font-weight: 800; color: #fff; }
    .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; color: white; }
</style>
""", unsafe_allow_html=True)

DB_FILE = "produtos_extras.json"
HIST_FILE = "historico.json"

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

def carregar_json(arquivo):
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "r") as f: return json.load(f)
        except: return []
    return []

def salvar_json(arquivo, dados):
    with open(arquivo, "w") as f: json.dump(dados, f, indent=4)

def capturar_loja(url, seletor, loja):
    if not url or len(url) < 10: return {"valor": 0.0, "estoque": "Sem URL"}
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Tenta localizar o binário do Chrome no servidor
    chrome_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if chrome_path:
        opts.binary_location = chrome_path

    try:
        # Tenta inicializar o driver
        if chrome_path:
            driver = webdriver.Chrome(options=opts)
        else:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
            
        driver.get(url)
        wait_time = 25 if "surya" in url.lower() else 15
        target_css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        
        WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, target_css)))
        time.sleep(5)
        
        texto = driver.find_element(By.CSS_SELECTOR, target_css).text.replace('\xa0', ' ').replace('\n', ' ')
        matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        precos = [float(m.replace('.', '').replace(',', '.')) for m in matches if float(m.replace('.', '').replace(',', '.')) > 1.0]
        
        if not precos: return {"valor": 0.0, "estoque": "Preço não lido"}

        # Lógica Vidafarma: Ignorar parcelas pegando o maior valor
        preco_final = max(precos) if "vidafarma" in url.lower() else min(precos)
        
        html = driver.page_source.lower()
        estoque = "✅ Disponível" if any(x in html for x in ['comprar', 'adicionar', 'estoque']) and not any(y in html for y in ['esgotado', 'indisponível']) else "❌ Esgotado"
        
        driver.quit()
        return {"valor": preco_final, "estoque": estoque}
    except Exception as e:
        if 'driver' in locals(): driver.quit()
        return {"valor": 0.0, "estoque": f"Erro: {str(e)[:15]}"}

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Market Overview", "⚙️ Configuração"])

with aba_config:
    st.subheader("Configuração de Produtos Extras")
    with st.form("form_add"):
        nome = st.text_input("Nome do Produto")
        v, cr, sp, sy = st.text_input("Link Vida"), st.text_input("Link Cremer"), st.text_input("Link Speed"), st.text_input("Link Surya")
        if st.form_submit_button("Salvar"):
            l = carregar_json(DB_FILE); l.append({"nome": nome, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
            salvar_json(DB_FILE, l); st.rerun()

with aba_dash:
    hist = carregar_json(HIST_FILE)
    
    if st.button("🔄 ATUALIZAR PREÇOS AGORA", use_container_width=True):
        todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        res_final = []
        
        # Para depuração e estabilidade, vamos processar um por um
        progresso = st.progress(0)
        for i, p in enumerate(todos):
            st.write(f"Buscando: {p['nome']}...")
            lojas_data = {}
            # Vidafarma
            lojas_data["Vidafarma"] = capturar_loja(p['vidafarma'], ".customProduct__price", "Vidafarma")
            lojas_data["Vidafarma"]["url"] = p['vidafarma']
            # Cremer
            lojas_data["Cremer"] = capturar_loja(p['cremer'], ".price", "Cremer")
            lojas_data["Cremer"]["url"] = p['cremer']
            # Speed
            lojas_data["Speed"] = capturar_loja(p['speed'], "[data-price-type='finalPrice']", "Speed")
            lojas_data["Speed"]["url"] = p['speed']
            # Surya
            lojas_data["Surya"] = capturar_loja(p['surya'], ".priceProduct-productPrice-2XFbc", "Surya")
            lojas_data["Surya"]["url"] = p['surya']
            
            res_final.append({"Produto": p['nome'], "lojas": lojas_data})
            progresso.progress((i + 1) / len(todos))
            
        salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": res_final}])
        st.rerun()

    if hist:
        dados = hist[0]['dados']
        # KPIs (Mesma lógica anterior)
        ganhando, empatados, perdendo, ruptura = 0, 0, 0, 0
        for p in dados:
            meu = p['lojas']['Vidafarma']['valor']
            if "❌" in p['lojas']['Vidafarma']['estoque']: ruptura += 1
            outros = [v['valor'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['valor'] > 1.0]
            if meu > 1.0 and outros:
                menor = min(outros)
                if meu < menor: ganhando += 1
                elif abs(meu - menor) < 0.1: empatados += 1
                else: perdendo += 1
        
        st.write("### 📈 Performance")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🟢 Ganhando", f"{(ganhando/len(dados))*100:.1f}%")
        k2.metric("🤝 Empatados", f"{(empatados/len(dados))*100:.1f}%")
        k3.metric("🔴 Perdendo", f"{(perdendo/len(dados))*100:.1f}%")
        k4.metric("⚪ Sua Ruptura", f"{(ruptura/len(dados))*100:.1f}%")
        st.divider()

        for p in dados:
            st.write(f"#### {p['Produto']}")
            cols = st.columns(4)
            for i, (nome_loja, info) in enumerate(p['lojas'].items()):
                with cols[i]:
                    cor_b = "#007BFF" if nome_loja == "Vidafarma" else "#333"
                    p_f = f"R$ {info['valor']:,.2f}".replace('.',',') if info['valor'] > 0 else "---"
                    st.markdown(f"""
                    <div class="shop-card" style="border-top: 4px solid {cor_b};">
                        <div style="color:#888; font-size:11px; font-weight:600;">{nome_loja}</div>
                        <div class="price-tag">{p_f}</div>
                        <div style="margin-top:8px;"><span class="status-badge" style="background:{'#238636' if '✅' in info['estoque'] else '#da3633'}">{info['estoque']}</span></div>
                        <div style="margin-top:10px;"><a href="{info['url']}" target="_blank" style="text-decoration:none; color:#58a6ff; font-size:12px;">Link ↗️</a></div>
                    </div>
                    """, unsafe_allow_html=True)
