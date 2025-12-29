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
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÃO SaaS PREMIUM ---
st.set_page_config(page_title="Dental Intel Pro", page_icon="📈", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; }
    .product-header { background: #21262d; padding: 12px 20px; border-radius: 8px 8px 0 0; border-left: 5px solid #007BFF; margin-top: 25px; color: #58a6ff; font-weight: 700; font-size: 18px; }
    .shop-card { background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; transition: 0.3s; height: 100%; border-top: 3px solid #333; }
    .shop-card:hover { border-color: #007BFF; transform: translateY(-3px); }
    .price-val { font-size: 26px; font-weight: 700; color: #fff; margin: 10px 0; }
    .status-badge { font-size: 10px; padding: 3px 10px; border-radius: 20px; color: white; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

HIST_FILE = "monitor_history.json"

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

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")
    # Otimização agressiva de memória
    options.add_argument("--js-flags='--max-old-space-size=512'")
    prefs = {"profile.managed_default_content_settings.images": 2, "profile.default_content_setting_values.notifications": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
        return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
    return webdriver.Chrome(options=options)

def capturar_com_retry(tarefa, retries=1):
    for i in range(retries + 1):
        res = capturar_loja(tarefa)
        if "ERRO" not in res[tarefa['loja']]['estoque']:
            return res
        time.sleep(2)
    return res

def capturar_loja(tarefa):
    url, loja_nome = tarefa['url'], tarefa['loja']
    if not url: return {loja_nome: {"preco": 0.0, "estoque": "N/A", "url": ""}}
    
    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        
        # Seletores
        if "vidafarma" in url.lower(): s = ".customProduct__price"
        elif "surya" in url.lower(): s = "p[class*='priceProduct-productPrice']"
        elif "speed" in url.lower(): s = "[data-price-type='finalPrice']"
        else: s = ".price"

        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CSS_SELECTOR, s)))
        time.sleep(3)
        
        texto = driver.find_element(By.CSS_SELECTOR, s).text.replace('\xa0', ' ')
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums]
        
        # Lógica de Preço Vidafarma (Máximo) vs Outros (Mínimo)
        preco = max(valores) if "vidafarma" in url.lower() else min(valores)
        
        html = driver.page_source.lower()
        estoque = "✅ DISPONÍVEL" if any(x in html for x in ['comprar', 'adicionar', 'estoque']) and not "indisponível" in html else "❌ ESGOTADO"
        
        return {loja_nome: {"preco": preco, "estoque": estoque, "url": url}}
    except:
        return {loja_nome: {"preco": 0.0, "estoque": "ERRO", "url": url}}
    finally:
        if driver: driver.quit()

def processar_produto_paralelo(p_config):
    tarefas = [
        {"url": p_config['vidafarma'], "loja": "Vidafarma"},
        {"url": p_config['cremer'], "loja": "Cremer"},
        {"url": p_config['speed'], "loja": "Speed"},
        {"url": p_config['surya'], "loja": "Surya"}
    ]
    # Reduzido para 2 workers para evitar crash de memória no Streamlit
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados_lista = list(executor.map(capturar_com_retry, tarefas))
    
    lojas_final = {}
    for r in resultados_lista: lojas_final.update(r)
    return {"nome": p_config['nome'], "lojas": lojas_final}

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Dashboard", "⚙️ Configurações"])

with aba_dash:
    if st.button("🚀 SINCRONIZAR PREÇOS (ESTÁVEL)", use_container_width=True):
        with st.status("Robôs analisando o mercado...", expanded=True) as status:
            resultados = []
            for p in PRODUTOS_FIXOS:
                st.write(f"Sincronizando: {p['nome']}...")
                resultados.append(processar_produto_paralelo(p))
            
            hist_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": resultados}
            with open(HIST_FILE, "w") as f: json.dump(hist_data, f)
            status.update(label="Sincronização Concluída!", state="complete")
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
                menor = min(concs)
                if meu < menor: ganhando += 1
                elif abs(meu - menor) < 0.1: empatados += 1
                else: perdendo += 1

        st.write("### 📈 Performance")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 Ganhando", ganhando)
        c2.metric("🤝 Empatados", empatados)
        c3.metric("🔴 Perdendo", perdendo)
        c4.metric("⚪ Sua Ruptura", ruptura)
        st.divider()

        for p in hist['produtos']:
            st.markdown(f'<div class="product-header">{p["nome"]}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for i, loja_nome in enumerate(["Vidafarma", "Cremer", "Speed", "Surya"]):
                info = p['lojas'][loja_nome]
                with cols[i]:
                    cor_top = "#007BFF" if loja_nome == "Vidafarma" else "#333"
                    p_f = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
                    st_bg = "#238636" if "✅" in info['estoque'] else "#da3633"
                    if info['estoque'] == "ERRO": st_bg = "#555"
                    
                    st.markdown(f"""
                    <div class="shop-card" style="border-top-color: {cor_top};">
                        <div style="color:#888; font-size:11px; font-weight:600;">{loja_nome}</div>
                        <div class="price-val">{p_f}</div>
                        <div style="margin-top:10px;"><span class="status-badge" style="background:{st_bg}">{info['estoque']}</span></div>
                        <div style="margin-top:12px;"><a href="{info['url']}" target="_blank" style="color:#58a6ff; font-size:12px; text-decoration:none;">Link ↗️</a></div>
                    </div>
                    """, unsafe_allow_html=True)
