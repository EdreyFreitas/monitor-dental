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

# --- CONFIGURAÇÃO DA INTERFACE SaaS ---
st.set_page_config(page_title="Dental Intel SaaS", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; border-left: 5px solid #007BFF; }
    .product-header { background: #21262d; padding: 12px 25px; border-radius: 10px; margin-top: 30px; color: #58a6ff; font-weight: 800; font-size: 18px; border: 1px solid #30363d; }
    .shop-tile { background: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; text-align: center; height: 100%; transition: 0.2s; }
    .shop-tile:hover { border-color: #58a6ff; background: #121d2f; }
    .price-val { font-size: 28px; font-weight: 800; color: #fff; margin: 10px 0; }
    .status-badge { font-size: 10px; padding: 3px 10px; border-radius: 20px; color: white; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

HIST_FILE = "monitor_history.json"
PRODUTOS_FIXOS = [
    {
        "nome": "Resina Z100 3M - A1",
        "links": [
            {"loja": "Vidafarma", "url": "https://dentalvidafarma.com.br/resina-z100-3m-solventum", "s": ".customProduct__price"},
            {"loja": "Cremer", "url": "https://www.dentalcremer.com.br/resina-z100tm-3m-solventum-dc10933.html", "s": ".price"},
            {"loja": "Speed", "url": "https://www.dentalspeed.com/resina-z100-3m-solventum-3369.html", "s": "[data-price-type='finalPrice']"},
            {"loja": "Surya", "url": "https://www.suryadental.com.br/resina-z100-4g-3m.html", "s": "p[class*='priceProduct-productPrice']"}
        ]
    },
    {
        "nome": "Anestésico Articaína DFL",
        "links": [
            {"loja": "Vidafarma", "url": "https://dentalvidafarma.com.br/anestesico-articaina-4-cv-1-100-000-dfl", "s": ".customProduct__price"},
            {"loja": "Cremer", "url": "https://www.dentalcremer.com.br/anest-articaine-1-100-000-c-50-dfl-361044.html", "s": ".price"},
            {"loja": "Speed", "url": "https://www.dentalspeed.com/anestesico-articaine-1-100-000-dfl.html", "s": "[data-price-type='finalPrice']"},
            {"loja": "Surya", "url": "https://www.suryadental.com.br/anestesico-articaine-1-100-000-dfl.html", "s": "p[class*='priceProduct-productPrice']"}
        ]
    }
]

# --- MOTOR SaaS DE ALTA PERFORMANCE ---
def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,720")
    # PERFORMANCE: Não carrega imagens nem CSS pesado
    opts.page_load_strategy = 'eager'
    prefs = {"profile.managed_default_content_settings.images": 2, "profile.default_content_setting_values.notifications": 2}
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    if os.path.exists("/usr/bin/chromium"):
        opts.binary_location = "/usr/bin/chromium"
        return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

def capturar_preco_saas(driver, url, seletor):
    try:
        driver.get(url)
        WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor)))
        
        texto = driver.find_element(By.CSS_SELECTOR, seletor).text.replace('\xa0', ' ')
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums if float(n.replace('.', '').replace(',', '.')) > 1.0]
        
        if not valores: return 0.0, "ERRO"

        # Lógica Vidafarma: Escolhe o maior valor (ignora parcelas)
        preco = max(valores) if "vidafarma" in url.lower() else min(valores)
        
        html = driver.page_source.lower()
        estoque = "✅ DISPONÍVEL" if any(x in html for x in ['comprar', 'adicionar']) and "esgotado" not in html else "❌ ESGOTADO"
        
        return preco, estoque
    except:
        return 0.0, "ERRO"

# --- LOGICA DE SINCRONIZAÇÃO ---
def iniciar_sincronizacao():
    driver = get_driver()
    resultados = []
    try:
        for item in PRODUTOS_FIXOS:
            st.write(f"🔍 Analisando: {item['nome']}")
            lojas_data = {}
            for link in item['links']:
                p, e = capturar_preco_saas(driver, link['url'], link['s'])
                lojas_data[link['loja']] = {"preco": p, "estoque": e, "url": link['url']}
            resultados.append({"nome": item['nome'], "dados": lojas_data})
        
        final_hist = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": resultados}
        with open(HIST_FILE, "w") as f: json.dump(final_hist, f)
        return final_hist
    finally:
        driver.quit()

# --- INTERFACE ---
st.title("⚡ Dental Intelligence Pro")

if st.button("🚀 SINCRONIZAR AGORA (ALTA VELOCIDADE)", use_container_width=True):
    hist = iniciar_sincronizacao()
    st.rerun()

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r") as f: hist = json.load(f)
    
    # KPIs
    ganhando, empatados, perdendo, ruptura = 0, 0, 0, 0
    for p in hist['produtos']:
        meu = p['dados']['Vidafarma']['preco']
        if "❌" in p['dados']['Vidafarma']['estoque']: ruptura += 1
        concs = [v['preco'] for k, v in p['dados'].items() if k != 'Vidafarma' and v['preco'] > 0]
        if meu > 0 and concs:
            menor_con = min(concs)
            if meu < menor_con: ganhando += 1
            elif abs(meu - menor_con) < 0.1: empatados += 1
            else: perdendo += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card" style="border-left-color:#28a745"><div style="color:#888;font-size:11px">GANHANDO</div><div class="price-val" style="margin:0">{ganhando}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card" style="border-left-color:#ffc107"><div style="color:#888;font-size:11px">EMPATADOS</div><div class="price-val" style="margin:0">{empatados}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card" style="border-left-color:#dc3545"><div style="color:#888;font-size:11px">PERDENDO</div><div class="price-val" style="margin:0">{perdendo}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card" style="border-left-color:#6c757d"><div style="color:#888;font-size:11px">SUA RUPTURA</div><div class="price-val" style="margin:0">{ruptura}</div></div>', unsafe_allow_html=True)
    st.caption(f"Última atualização: {hist['data']}")
    st.divider()

    for p in hist['produtos']:
        st.markdown(f'<div class="product-header">{p["nome"]}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, loja in enumerate(["Vidafarma", "Cremer", "Speed", "Surya"]):
            info = p['dados'][loja]
            with cols[i]:
                cor = "#007BFF" if loja == "Vidafarma" else "#333"
                p_txt = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
                st_bg = "#238636" if "✅" in info['estoque'] else "#da3633"
                if info['estoque'] == "ERRO": st_bg = "#555"
                st.markdown(f"""
                <div class="shop-tile" style="border-top: 3px solid {cor};">
                    <div style="color:#888; font-size:11px; font-weight:600;">{loja.upper()}</div>
                    <div class="price-val">{p_txt}</div>
                    <div style="margin-top:10px;"><span class="status-badge" style="background:{st_bg}">{info['estoque']}</span></div>
                    <div style="margin-top:12px;"><a href="{info['url']}" target="_blank" style="color:#58a6ff; font-size:12px; text-decoration:none;">Ver Produto ↗️</a></div>
                </div>
                """, unsafe_allow_html=True)
