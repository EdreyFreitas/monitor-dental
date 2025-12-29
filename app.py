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
st.set_page_config(page_title="Dental Intelligence Pro", page_icon="📈", layout="wide")

# UI/UX SaaS CUSTOMIZADA
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    
    .stButton>button {
        background: #007BFF; color: white; border-radius: 8px; font-weight: 700; width: 100%;
    }
    
    .kpi-box {
        background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; text-align: center;
    }

    .product-section {
        background: #161b22; padding: 15px; border-radius: 10px 10px 0 0;
        border-left: 4px solid #007BFF; margin-top: 30px; font-weight: 700;
    }

    .shop-card {
        background: #0d1117; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; text-align: center; height: 100%; transition: 0.3s;
    }
    .shop-card:hover { border-color: #58a6ff; }

    .price-tag { font-size: 24px; font-weight: 800; color: #f0f6fc; margin: 10px 0; }
    .shop-name { color: #8b949e; font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 1px; }
    
    .status-ok { color: #3fb950; font-size: 12px; font-weight: 600; }
    .status-err { color: #f85149; font-size: 12px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAÇÃO DE DADOS ---
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

# --- MOTOR DE SCRAPING (VERSÃO BLINDADA) ---
def capturar_loja(tarefa):
    url, seletor, loja = tarefa['url'], tarefa['seletor'], tarefa['loja']
    if not url or len(url) < 10: return {"loja": loja, "valor": 0.0, "estoque": "Sem Link", "url": url}
    
    driver = None
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # Lógica para detectar se está no Streamlit Cloud ou Local
        if os.path.exists("/usr/bin/chromium-browser"):
            opts.binary_location = "/usr/bin/chromium-browser"
            driver = webdriver.Chrome(options=opts)
        else:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
        
        driver.get(url)
        wait_time = 20 if "surya" in url.lower() else 15
        target_css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        
        WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, target_css)))
        time.sleep(5) 
        
        elemento = driver.find_element(By.CSS_SELECTOR, target_css)
        texto = elemento.text.replace('\xa0', ' ').replace('\n', ' ')
        
        matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        precos = [float(m.replace('.', '').replace(',', '.')) for m in matches if float(m.replace('.', '').replace(',', '.')) > 1.0]
        
        if not precos: return {"loja": loja, "valor": 0.0, "estoque": "Preço oculto", "url": url}

        # Lógica específica Vidafarma: Ignorar parcelas pegando o maior valor
        preco_final = max(precos) if "vidafarma" in url.lower() else min(precos)
            
        html = driver.page_source.lower()
        est = "✅ Disponível" if any(x in html for x in ['comprar', 'adicionar', 'estoque']) and not any(y in html for y in ['esgotado', 'indisponível']) else "❌ Esgotado"
            
        return {"loja": loja, "valor": preco_final, "estoque": est, "url": url}
    except Exception as e:
        return {"loja": loja, "valor": 0.0, "estoque": "Erro", "url": url}
    finally:
        if driver: driver.quit()

# --- INTERFACE ---
tab_dash, tab_config = st.tabs(["📊 Inteligência de Mercado", "⚙️ Configurações"])

with tab_config:
    st.subheader("Cadastro de Itens Extras")
    with st.form("form_add"):
        n = st.text_input("Nome do Produto")
        c1, c2 = st.columns(2)
        v, cr = c1.text_input("Link Vidafarma"), c2.text_input("Link Cremer")
        sp, sy = c1.text_input("Link Speed"), c2.text_input("Link Surya")
        if st.form_submit_button("Salvar Produto"):
            if n and v:
                l = carregar_json(DB_FILE); l.append({"nome": n, "vidafarma": v, "cremer": cr, "speed": sp, "surya": sy})
                salvar_json(DB_FILE, l); st.rerun()

with tab_dash:
    hist = carregar_json(HIST_FILE)
    
    if st.button("🔄 ATUALIZAR TODOS OS PREÇOS AGORA"):
        todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        tarefas = []
        for p in todos:
            tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
            tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
            tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
            tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

        with st.status("Robôs sincronizando...", expanded=True):
            with ThreadPoolExecutor(max_workers=3) as executor:
                brutos = list(executor.map(capturar_loja, tarefas))
            
            res = {}
            for i, t in enumerate(tarefas):
                pid = t['id']
                if pid not in res: res[pid] = {"Produto": pid, "lojas": {}}
                res[pid]["lojas"][t['loja']] = brutos[i]
            
            salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": list(res.values())}])
            st.rerun()

    if hist:
        dados = hist[0]['dados']
        ganhando, perdendo, empatados, ruptura = 0, 0, 0, 0
        
        for p in dados:
            meu = p['lojas']['Vidafarma']['valor']
            if "❌" in p['lojas']['Vidafarma']['estoque']: ruptura += 1
            concs = [v['valor'] for k, v in p['lojas'].items() if k != 'Vidafarma' and v['valor'] > 1.0]
            if meu > 1.0 and concs:
                menor = min(concs)
                if meu < menor: ganhando += 1
                elif abs(meu - menor) < 0.1: empatados += 1
                else: perdendo += 1

        st.write("### 📈 Performance da Vitrine")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 Ganhando", f"{(ganhando/len(dados))*100:.1f}%")
        c2.metric("🤝 Empatados", f"{(empatados/len(dados))*100:.1f}%")
        c3.metric("🔴 Perdendo", f"{(perdendo/len(dados))*100:.1f}%")
        c4.metric("⚪ Sua Ruptura", f"{(ruptura/len(dados))*100:.1f}%")
        st.caption(f"Última atualização: {hist[0]['data']}")
        st.divider()

        for p in dados:
            st.markdown(f'<div class="product-section">{p["Produto"]}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for i, (loja, info) in enumerate(p['lojas'].items()):
                with cols[i]:
                    cor = "#007BFF" if loja == "Vidafarma" else "#30363d"
                    p_format = f"R$ {info['valor']:,.2f}".replace('.',',') if info['valor'] > 0 else "---"
                    status_cl = "status-ok" if "✅" in info['estoque'] else "status-err"
                    
                    st.markdown(f"""
                    <div class="shop-card" style="border-top: 3px solid {cor};">
                        <div class="shop-name">{loja}</div>
                        <div class="price-tag">{p_format}</div>
                        <div class="{status_cl}">{info['estoque']}</div>
                        <div style="margin-top:10px;"><a href="{info['url']}" target="_blank" style="text-decoration:none; color:#58a6ff; font-size:12px;">Ver no Site ↗️</a></div>
                    </div>
                    """, unsafe_allow_html=True)
