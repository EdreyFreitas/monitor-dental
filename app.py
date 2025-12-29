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
st.set_page_config(page_title="Dental Intelligence SaaS", page_icon="📈", layout="wide")

# UI PREMIUM SaaS (CSS CUSTOMIZADO)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; }
    .product-header { background: #21262d; padding: 12px 20px; border-radius: 8px 8px 0 0; border-left: 5px solid #007BFF; margin-top: 25px; color: #58a6ff; font-weight: 700; font-size: 18px; }
    
    .shop-card { background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; transition: 0.3s; height: 100%; }
    .shop-card:hover { border-color: #007BFF; transform: translateY(-3px); }
    
    .price-val { font-size: 26px; font-weight: 700; color: #fff; margin: 10px 0; }
    .shop-label { color: #888; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    
    .status-badge { font-size: 10px; padding: 3px 10px; border-radius: 20px; color: white; font-weight: 700; }
    .link-icon { color: #58a6ff; text-decoration: none; font-size: 14px; margin-top: 10px; display: inline-block; }
</style>
""", unsafe_allow_html=True)

HIST_FILE = "monitor_history.json"

# --- CURVA A (FIXA) ---
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

# --- MOTOR DE NAVEGAÇÃO ---
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Caminho específico para o Chromium no Streamlit Cloud
    options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
    
    return webdriver.Chrome(service=service, options=options)

def capturar_loja(url, loja_nome):
    if not url: return {"preco": 0.0, "estoque": "N/A", "url": ""}
    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        
        # Seletores Inteligentes
        if "vidafarma" in url: s = ".customProduct__price"
        elif "surya" in url: s = "p[class*='priceProduct-productPrice']"
        elif "speed" in url: s = "[data-price-type='finalPrice']"
        else: s = ".price"

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, s)))
        time.sleep(5)
        
        texto = driver.find_element(By.CSS_SELECTOR, s).text.replace('\xa0', ' ')
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums]
        
        # LÓGICA VIDAFARMA: Pega o maior valor (Total) e ignora parcelas
        if "vidafarma" in url:
            preco = max(valores) if valores else 0.0
        else:
            preco = min(valores) if valores else 0.0
        
        html = driver.page_source.lower()
        estoque = "✅ DISPONÍVEL" if "adicionar" in html or "comprar" in html else "❌ ESGOTADO"
        
        return {"preco": preco, "estoque": estoque, "url": url}
    except Exception as e:
        return {"preco": 0.0, "estoque": "ERRO", "url": url}
    finally:
        if driver: driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Dashboard de Performance", "⚙️ Configurações"])

with aba_dash:
    col_t, col_b = st.columns([3, 1])
    with col_t: st.write("## 🏛️ Central de Inteligência de Mercado")
    
    if col_b.button("🔄 SINCRONIZAR", use_container_width=True):
        resultados = []
        for p in PRODUTOS_FIXOS:
            with st.spinner(f"Analisando {p['nome']}..."):
                res_lojas = {
                    "Vidafarma": capturar_loja(p['vidafarma'], "vidafarma"),
                    "Cremer": capturar_loja(p['cremer'], "cremer"),
                    "Speed": capturar_loja(p['speed'], "speed"),
                    "Surya": capturar_loja(p['surya'], "surya")
                }
                resultados.append({"nome": p['nome'], "lojas": res_lojas})
        
        hist_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": resultados}
        with open(HIST_FILE, "w") as f: json.dump(hist_data, f)
        st.rerun()

    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r") as f: hist = json.load(f)
        
        # --- CÁLCULOS KPI ---
        ganhando, empatados, perdendo, ruptura = 0, 0, 0, 0
        for p in hist['produtos']:
            meu = p['lojas']['Vidafarma']['preco']
            if "❌" in p['lojas']['Vidafarma']['estoque']: ruptura += 1
            outros = [v['preco'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['preco'] > 0]
            if meu > 0 and outros:
                menor_con = min(outros)
                if meu < menor_con: ganhando += 1
                elif abs(meu - menor_con) < 0.1: empatados += 1
                else: perdendo += 1

        total = len(hist['produtos'])
        st.write("### 📈 Visão Geral da Conta")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="kpi-card" style="border-left-color:#28a745"><div style="color:#888;font-size:11px">GANHANDO</div><div style="font-size:26px;font-weight:700">{ganhando}</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="kpi-card" style="border-left-color:#ffc107"><div style="color:#888;font-size:11px">EMPATADOS</div><div style="font-size:26px;font-weight:700">{empatados}</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="kpi-card" style="border-left-color:#dc3545"><div style="color:#888;font-size:11px">PERDENDO</div><div style="font-size:26px;font-weight:700">{perdendo}</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="kpi-card" style="border-left-color:#6c757d"><div style="color:#888;font-size:11px">RUPTURA</div><div style="font-size:26px;font-weight:700">{ruptura}</div></div>', unsafe_allow_html=True)
        
        st.caption(f"Sincronizado em: {hist['data']}")
        st.divider()

        # --- CARDS DE PRODUTO ---
        for p in hist['produtos']:
            st.markdown(f'<div class="product-header">{p["nome"]}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for i, (loja, info) in enumerate(p['lojas'].items()):
                with cols[i]:
                    cor_top = "#007BFF" if loja == "Vidafarma" else "#333"
                    preco_f = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
                    badge_bg = "#238636" if "✅" in info['estoque'] else "#da3633"
                    if info['estoque'] == "ERRO": badge_bg = "#555"
                    
                    st.markdown(f"""
                    <div class="shop-card" style="border-top: 4px solid {cor_top};">
                        <div class="shop-label">{loja}</div>
                        <div class="price-val">{preco_f}</div>
                        <div style="margin-top:10px;"><span class="status-badge" style="background:{badge_bg}">{info['estoque']}</span></div>
                        <a href="{info['url']}" target="_blank" class="link-icon">Acessar Loja ↗️</a>
                    </div>
                    """, unsafe_allow_html=True)
