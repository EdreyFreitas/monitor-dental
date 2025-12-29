import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import re
import time
import json
import os
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dental Intel Pro", page_icon="📈", layout="wide")

# Estilização CSS SaaS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; }
    .product-title { background: #21262d; padding: 10px 20px; border-radius: 8px 8px 0 0; border-left: 5px solid #007BFF; margin-top: 25px; color: #58a6ff; font-weight: 700; font-size: 18px; }
    .shop-card { background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; transition: 0.3s; height: 100%; border-top: 3px solid #333; }
    .price-val { font-size: 26px; font-weight: 700; color: #fff; margin: 10px 0; }
    .status-badge { font-size: 10px; padding: 3px 10px; border-radius: 20px; color: white; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

HIST_FILE = "monitor_history.json"

# --- PRODUTOS CURVA A (FIXOS) ---
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

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Caminho Chromium Streamlit Cloud
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
        return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
    # Execução local
    return webdriver.Chrome(options=options)

def capturar_dados(url, loja):
    if not url: return {"preco": 0.0, "estoque": "N/A", "url": ""}
    driver = get_driver()
    try:
        driver.get(url)
        # Seletores estáveis
        if "vidafarma" in url: s = ".customProduct__price"
        elif "surya" in url: s = "p[class*='priceProduct-productPrice']"
        elif "speed" in url: s = "[data-price-type='finalPrice']"
        else: s = ".price"

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, s)))
        time.sleep(4) # Tempo para JS
        
        texto = driver.find_element(By.CSS_SELECTOR, s).text.replace('\xa0', ' ').replace('\n', ' ')
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums]
        
        # LOGICA DE PREÇO: Na Vidafarma pega o maior (Total), nos outros o menor (Pix)
        preco = max(valores) if "vidafarma" in url else min(valores)
        
        html = driver.page_source.lower()
        estoque = "✅ DISPONÍVEL" if "adicionar" in html or "comprar" in html else "❌ ESGOTADO"
        return {"preco": preco, "estoque": estoque, "url": url}
    except:
        return {"preco": 0.0, "estoque": "ERRO", "url": url}
    finally:
        driver.quit()

# --- INTERFACE ---
st.title("📊 Dental Intel | SaaS Dashboard")

if st.button("🚀 ATUALIZAR PREÇOS AGORA", use_container_width=True):
    resultados = []
    for p in PRODUTOS_FIXOS:
        with st.spinner(f"Analisando {p['nome']}..."):
            lojas_res = {
                "Vidafarma": capturar_dados(p['vidafarma'], "vidafarma"),
                "Cremer": capturar_dados(p['cremer'], "cremer"),
                "Speed": capturar_dados(p['speed'], "speed"),
                "Surya": capturar_dados(p['surya'], "surya")
            }
            resultados.append({"nome": p['nome'], "lojas": lojas_res})
    
    hist_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": resultados}
    with open(HIST_FILE, "w") as f: json.dump(hist_data, f)
    st.rerun()

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r") as f: hist = json.load(f)
    
    # KPIs
    ganhando, empatados, perdendo, ruptura = 0, 0, 0, 0
    for p in hist['produtos']:
        meu = p['lojas']['Vidafarma']['preco']
        if "❌" in p['lojas']['Vidafarma']['estoque']: ruptura += 1
        concs = [v['preco'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['preco'] > 0]
        if meu > 0 and concs:
            menor_con = min(concs)
            if meu < menor_con: ganhando += 1
            elif abs(meu - menor_con) < 0.1: empatados += 1
            else: perdendo += 1

    # Dashboard de Indicadores
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card" style="border-left-color:#28a745"><div style="color:#888;font-size:11px">GANHANDO</div><div style="font-size:26px;font-weight:700">{ganhando}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card" style="border-left-color:#ffc107"><div style="color:#888;font-size:11px">EMPATADOS</div><div style="font-size:26px;font-weight:700">{empatados}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card" style="border-left-color:#dc3545"><div style="color:#888;font-size:11px">PERDENDO</div><div style="font-size:26px;font-weight:700">{perdendo}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card" style="border-left-color:#6c757d"><div style="color:#888;font-size:11px">SUA RUPTURA</div><div style="font-size:26px;font-weight:700">{ruptura}</div></div>', unsafe_allow_html=True)
    
    st.caption(f"Sincronizado em: {hist['data']}")
    st.divider()

    # Cards de Produtos
    for p in hist['produtos']:
        st.markdown(f'<div class="product-title">{p["nome"]}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, loja_nome in enumerate(["Vidafarma", "Cremer", "Speed", "Surya"]):
            info = p['lojas'][loja_nome]
            with cols[i]:
                cor_top = "#007BFF" if loja_nome == "Vidafarma" else "#333"
                preco_f = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
                st_bg = "#238636" if "✅" in info['estoque'] else "#da3633"
                if info['estoque'] == "ERRO": st_bg = "#555"
                
                st.markdown(f"""
                <div class="shop-card" style="border-top-color: {cor_top};">
                    <div style="color:#888; font-size:11px; font-weight:600; text-transform:uppercase;">{loja_nome}</div>
                    <div class="price-val">{preco_f}</div>
                    <div style="margin-top:10px;"><span class="status-badge" style="background:{st_bg}">{info['estoque']}</span></div>
                    <div style="margin-top:12px;"><a href="{info['url']}" target="_blank" style="color:#58a6ff; font-size:12px; text-decoration:none;">Acessar Loja ↗️</a></div>
                </div>
                """, unsafe_allow_html=True)
