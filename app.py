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

# --- CONFIGURAÇÃO DA INTERFACE (ESTILO SaaS DARK) ---
st.set_page_config(page_title="Dental Intel | Dashboard", page_icon="📈", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    
    /* Indicadores de Topo */
    .kpi-card {
        background: #161b22; border: 1px solid #30363d; padding: 20px;
        border-radius: 10px; text-align: center;
    }
    .kpi-value { font-size: 28px; font-weight: 700; color: #ffffff; }
    .kpi-label { font-size: 12px; color: #8b949e; text-transform: uppercase; margin-top: 5px; }

    /* Cards de Produto */
    .product-container {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 12px; margin-bottom: 30px; overflow: hidden;
    }
    .product-header {
        background: #21262d; padding: 15px 25px; border-bottom: 1px solid #30363d;
        font-weight: 700; font-size: 18px; color: #58a6ff;
    }
    .grid-container { display: grid; grid-template-columns: repeat(4, 1fr); padding: 20px; gap: 20px; }
    
    .store-box {
        background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
        padding: 20px; text-align: center; transition: 0.3s;
    }
    .store-box:hover { border-color: #58a6ff; background: #121d2f; }
    
    .price-main { font-size: 24px; font-weight: 700; color: #fff; margin: 10px 0; }
    .store-name { color: #8b949e; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .badge-status { font-size: 10px; padding: 3px 8px; border-radius: 20px; font-weight: 700; }
    
    a { text-decoration: none; color: #58a6ff; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS FIXO (CURVA A) ---
PRODUTOS_MONITORADOS = [
    {
        "id": "resina-z100",
        "nome": "Resina Z100 3M - Kit Variações",
        "links": {
            "Vidafarma": "https://dentalvidafarma.com.br/resina-z100-3m-solventum",
            "Cremer": "https://www.dentalcremer.com.br/resina-z100tm-3m-solventum-dc10933.html",
            "Speed": "https://www.dentalspeed.com/resina-z100-3m-solventum-3369.html",
            "Surya": "https://www.suryadental.com.br/resina-z100-4g-3m.html"
        }
    },
    {
        "id": "articaina-dfl",
        "nome": "Anestésico Articaína 4% DFL",
        "links": {
            "Vidafarma": "https://dentalvidafarma.com.br/anestesico-articaina-4-cv-1-100-000-dfl",
            "Cremer": "https://www.dentalcremer.com.br/anest-articaine-1-100-000-c-50-dfl-361044.html",
            "Speed": "https://www.dentalspeed.com/anestesico-articaine-1-100-000-dfl.html",
            "Surya": "https://www.suryadental.com.br/anestesico-articaine-1-100-000-dfl.html"
        }
    }
]

HIST_FILE = "monitor_history.json"

# --- MOTOR DE INTELIGÊNCIA ---
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Disfarça o robô
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # Tenta modo nuvem
        options.binary_location = "/usr/bin/chromium-browser"
        return webdriver.Chrome(options=options)
    except:
        # Tenta modo local
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def buscar_preco(loja, url):
    if not url: return {"preco": 0.0, "estoque": "N/A"}
    
    driver = get_driver()
    try:
        driver.get(url)
        # Seletores dinâmicos
        if "vidafarma" in url:
            selector = ".customProduct__price"
        elif "surya" in url:
            selector = "p[class*='priceProduct-productPrice']"
        elif "speed" in url:
            selector = "[data-price-type='finalPrice']"
        else:
            selector = ".price"

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        time.sleep(5) # Tempo para renderizar preços finais
        
        texto = driver.find_element(By.CSS_SELECTOR, selector).text
        # Extrai todos os valores numéricos
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums]
        
        # Lógica especial Vidafarma (ignora parcela pegando o maior)
        if "vidafarma" in url:
            preco_final = max(valores) if valores else 0.0
        else:
            preco_final = min(valores) if valores else 0.0

        html = driver.page_source.lower()
        estoque = "✅ DISPONÍVEL" if "adicionar" in html or "comprar" in html else "❌ ESGOTADO"
        
        return {"preco": preco_final, "estoque": estoque}
    except:
        return {"preco": 0.0, "estoque": "ERRO"}
    finally:
        driver.quit()

# --- LOGICA DE PROCESSAMENTO ---
def executar_varredura():
    resultados = []
    for item in PRODUTOS_MONITORADOS:
        with st.spinner(f"Analisando {item['nome']}..."):
            lojas_res = {}
            for loja, url in item['links'].items():
                lojas_res[loja] = buscar_preco(loja, url)
                lojas_res[loja]['url'] = url
            resultados.append({"nome": item['nome'], "dados": lojas_res})
    
    # Salva histórico
    final_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": resultados}
    with open(HIST_FILE, "w") as f: json.dump(final_data, f)
    return final_data

# --- UI ---
st.title("📊 Dental Market Intelligence")
st.write("Sincronização em tempo real com os principais players do mercado.")

if st.button("🔄 SINCRONIZAR AGORA"):
    hist = executar_varredura()
    st.rerun()
else:
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r") as f: hist = json.load(f)
    else:
        hist = None

if hist:
    # --- KPIs ---
    prods = hist['produtos']
    ganhando, empatados, perdendo, ruptura = 0, 0, 0, 0
    
    for p in prods:
        meu = p['dados']['Vidafarma']['preco']
        if "❌" in p['dados']['Vidafarma']['estoque']: ruptura += 1
        
        concorrentes = [v['preco'] for k, v in p['dados'].items() if k != 'Vidafarma' and v['preco'] > 0]
        if meu > 0 and concorrentes:
            menor_con = min(concorrentes)
            if meu < menor_con: ganhando += 1
            elif abs(meu - menor_con) < 0.05: empatados += 1
            else: perdendo += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-value">{ganhando}</div><div class="kpi-label">Ganhando</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card" style="border-left-color: #f1e05a"><div class="kpi-value">{empatados}</div><div class="kpi-label">Empatados</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card" style="border-left-color: #f85149"><div class="kpi-value">{perdendo}</div><div class="kpi-label">Perdendo</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card" style="border-left-color: #8b949e"><div class="kpi-value">{ruptura}</div><div class="kpi-label">Ruptura</div></div>', unsafe_allow_html=True)
    
    st.caption(f"Última atualização: {hist['data']}")
    st.divider()

    # --- CARDS ---
    for p in prods:
        st.markdown(f"""
        <div class="product-container">
            <div class="product-header">{p['nome']}</div>
            <div class="grid-container">
        """, unsafe_allow_html=True)
        
        cols = st.columns(4)
        lojas = ["Vidafarma", "Cremer", "Speed", "Surya"]
        
        for i, loja in enumerate(lojas):
            info = p['dados'][loja]
            preco_txt = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
            cor_badge = "#238636" if "✅" in info['estoque'] else "#da3633"
            if info['estoque'] == "ERRO": cor_badge = "#8b949e"
            
            with cols[i]:
                st.markdown(f"""
                <div class="store-box">
                    <div class="store-name">{loja}</div>
                    <div class="price-main">{preco_txt}</div>
                    <div style="margin: 10px 0;"><span class="badge-status" style="background: {cor_badge}; color: white;">{info['estoque']}</span></div>
                    <a href="{info['url']}" target="_blank">Acessar Loja ↗️</a>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)
else:
    st.info("Clique no botão de sincronização para carregar os dados pela primeira vez.")
