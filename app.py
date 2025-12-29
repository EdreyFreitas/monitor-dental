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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dental Intelligence SaaS", page_icon="⚡", layout="wide")

# MANTENDO SUA INTERFACE (CSS SaaS PREMIUM)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; border-top: 4px solid #007BFF; }
    .product-header { background: #21262d; padding: 10px 20px; border-radius: 8px 8px 0 0; margin-top: 25px; color: #58a6ff; font-weight: 700; font-size: 18px; border: 1px solid #30363d; }
    .shop-card { background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; transition: 0.3s; height: 100%; border-top: 3px solid #333; }
    .price-val { font-size: 26px; font-weight: 700; color: #fff; margin: 10px 0; }
    .status-badge { font-size: 10px; padding: 3px 10px; border-radius: 20px; color: white; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

HIST_FILE = "monitor_history.json"
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

# --- MOTOR SaaS ULTRA-FAST ---
def get_optimized_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    
    # ACELERAÇÃO MÁXIMA: Ignora imagens, css e fontes
    opts.page_load_strategy = 'eager' 
    prefs = {"profile.managed_default_content_settings.images": 2, "profile.default_content_setting_values.notifications": 2}
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    if os.path.exists("/usr/bin/chromium"):
        opts.binary_location = "/usr/bin/chromium"
        return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

def capturar_dados_saas(driver, url):
    if not url: return 0.0, "Sem URL"
    try:
        driver.get(url)
        # Seletores dinâmicos
        if "vidafarma" in url: s = ".customProduct__price"
        elif "surya" in url: s = "p[class*='priceProduct-productPrice']"
        elif "speed" in url: s = "[data-price-type='finalPrice']"
        else: s = ".price"

        # Espera o preço aparecer na tela por no máx 8 segundos
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, s)))
        
        # Pega todos os valores numéricos daquela área
        elemento = driver.find_element(By.CSS_SELECTOR, s)
        texto = elemento.text.replace('\xa0', ' ').replace('\n', ' ')
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums if float(n.replace('.', '').replace(',', '.')) > 1.0]
        
        # LOGICA ARTICAINA: Na Vidafarma pega o maior (Total), nos outros o menor (Pix)
        preco = max(valores) if "vidafarma" in url and valores else (min(valores) if valores else 0.0)
        
        # ESTOQUE: Procura botões de ação positiva
        html = driver.page_source.lower()
        estoque = "✅ DISPONÍVEL" if "adicionar" in html or "comprar" in html else "❌ ESGOTADO"
        
        return preco, estoque
    except:
        return 0.0, "ERRO"

# --- SINCRONIZAÇÃO EM CADEIA (REUSANDO O NAVEGADOR) ---
def sincronizar_tudo():
    driver = get_optimized_driver()
    resultados = []
    try:
        for p in PRODUTOS_FIXOS:
            st.write(f"⚡ Sincronizando: {p['nome']}")
            lojas = {}
            for loja_nome in ["vidafarma", "cremer", "speed", "surya"]:
                preco, estoque = capturar_dados_saas(driver, p[loja_nome])
                lojas[loja_nome.capitalize()] = {"preco": preco, "estoque": estoque, "url": p[loja_nome]}
            resultados.append({"nome": p['nome'], "lojas": lojas})
        
        final_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": resultados}
        with open(HIST_FILE, "w") as f: json.dump(final_data, f)
        return final_data
    finally:
        driver.quit()

# --- INTERFACE ---
st.title("⚡ Dental Intelligence SaaS")

if st.button("🚀 ATUALIZAR PREÇOS AGORA (SUB-10s)", use_container_width=True):
    hist = sincronizar_tudo()
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

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card" style="border-top-color:#28a745">GANHANDO<div class="price-val">{ganhando}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card" style="border-top-color:#ffc107">EMPATADOS<div class="price-val">{empatados}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card" style="border-top-color:#dc3545">PERDENDO<div class="price-val">{perdendo}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card" style="border-top-color:#6c757d">RUPTURA<div class="price-val">{ruptura}</div></div>', unsafe_allow_html=True)
    
    st.divider()

    for p in hist['produtos']:
        st.markdown(f'<div class="product-header">{p["nome"]}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, loja in enumerate(["Vidafarma", "Cremer", "Speed", "Surya"]):
            info = p['lojas'][loja]
            with cols[i]:
                cor = "#007BFF" if loja == "Vidafarma" else "#333"
                p_txt = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
                st_bg = "#238636" if "✅" in info['estoque'] else "#da3633"
                if info['estoque'] == "ERRO": st_bg = "#555"
                st.markdown(f"""
                <div class="shop-card" style="border-top-color: {cor};">
                    <div style="color:#888; font-size:11px; font-weight:600;">{loja.upper()}</div>
                    <div class="price-val">{p_txt}</div>
                    <div style="margin-top:10px;"><span class="status-badge" style="background:{st_bg}">{info['estoque']}</span></div>
                    <div style="margin-top:12px;"><a href="{info['url']}" target="_blank" style="color:#58a6ff; font-size:12px; text-decoration:none;">Conferir ↗️</a></div>
                </div>
                """, unsafe_allow_html=True)
