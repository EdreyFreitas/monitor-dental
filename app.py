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
st.set_page_config(page_title="Monitor Dental Flash", page_icon="⚡", layout="wide")

# ==========================================================
# 🟢 SUA CURVA A (PRODUTOS FIXOS)
# ==========================================================
PRODUTOS_FIXOS = [
    {
        "nome": "Resina Z100 3M - A1",
        "vidafarma": "https://dentalvidafarma.com.br/resina-z100-3m-solventum",
        "cremer": "https://www.dentalcremer.com.br/resina-z100tm-3m-solventum-dc10933.html",
        "speed": "https://www.dentalspeed.com/resina-z100-3m-solventum-3369.html",
        "surya": "https://www.suryadental.com.br/resina-z100-4g-3m.html"
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
    if not url: return {"loja": loja, "valor": "N/A", "url": ""}
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,720")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except:
        driver = webdriver.Chrome(options=opts)
    
    try:
        driver.get(url)
        wait_time = 20 if "surya" in url.lower() else 15
        css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
        time.sleep(3)
        elementos = driver.find_elements(By.CSS_SELECTOR, css)
        precos = []
        for el in elementos:
            t = el.text.replace(' ', '').replace('\xa0', '').replace('\n', '')
            m = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', t)
            precos.extend([float(v.replace('.', '').replace(',', '.')) for v in m])
        
        p_final = min(precos) if precos else 0.0
        html = driver.page_source.lower()
        if "vidafarma" in url.lower():
            est = "✅" if "comprar" in html or "adicionar" in html else "❌"
        else:
            esg = any(t in html for t in ['esgotado', 'indisponível', 'avise', 'fora de estoque'])
            est = "❌" if esg else "✅"
        return {"loja": loja, "valor": f"R$ {p_final:,.2f} {est}".replace('.',','), "url": url}
    except:
        return {"loja": loja, "valor": "Erro ❌", "url": url}
    finally:
        driver.quit()

# --- INTERFACE ---
aba_dash, aba_config = st.tabs(["📊 Dashboard de Conferência", "⚙️ Gerenciar Extras"])

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
    
    for i, p in enumerate(carregar_json(DB_FILE)):
        c1, c2 = st.columns([5,1])
        c1.write(f"📦 {p['nome']}")
        if c2.button("Remover", key=f"del_{i}"):
            ex = carregar_json(DB_FILE); ex.pop(i); salvar_json(DB_FILE, ex); st.rerun()

with aba_dash:
    hist = carregar_json(HIST_FILE)
    
    if st.button("🚀 ATUALIZAR PREÇOS"):
        todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        if todos:
            tarefas = []
            for p in todos:
                tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
                tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
                tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
                tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

            with st.status("Processando...", expanded=True):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    brutos = list(executor.map(capturar_loja, tarefas))
                matriz = {}
                for i, t in enumerate(tarefas):
                    pid = t['id']
                    if pid not in matriz: matriz[pid] = {"Produto": pid}
                    matriz[pid][t['loja']] = brutos[i]['valor']
                    matriz[pid][f"L_{t['loja']}"] = brutos[i]['url']
                salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": list(matriz.values())}])
                st.rerun()

    if hist:
        df = pd.DataFrame(hist[0]['dados'])
        
        # --- CÁLCULOS INDICADORES ---
        def extrair_v(texto):
            try:
                num = re.search(r'R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', str(texto))
                return float(num.group(1).replace('.', '').replace(',', '.')) if num else None
            except: return None

        total = len(df)
        ganhando, perdendo, ruptura = 0, 0, 0
        for _, row in df.iterrows():
            meu_p = extrair_v(row['Vidafarma'])
            if "❌" in str(row['Vidafarma']): ruptura += 1
            concs = [extrair_v(row[c]) for c in ['Cremer', 'Speed', 'Surya'] if extrair_v(row[c])]
            if meu_p and concs:
                if meu_p < min(concs): ganhando += 1
                elif meu_p > min(concs): perdendo += 1
        
        p_ganh = (ganhando/total)*100 if total>0 else 0
        p_perd = (perdendo/total)*100 if total>0 else 0
        p_rupt = (ruptura/total)*100 if total>0 else 0

        def criar_barra(label, percent, cor):
            st.markdown(f"""<div style="margin-bottom: 10px;"><div style="display: flex; justify-content: space-between; margin-bottom: 2px;"><span style="font-size: 13px; font-weight: bold;">{label}</span><span style="font-size: 13px;">{percent:.1f}%</span></div><div style="background-color: #333; border-radius: 5px; width: 100%; height: 10px;"><div style="background-color: {cor}; width: {percent}%; height: 100%; border-radius: 5px;"></div></div></div>""", unsafe_allow_html=True)

        st.subheader("📊 Performance")
        c1, c2, c3 = st.columns(3)
        with c1: criar_barra("🟢 Ganhando", p_ganh, "#28a745")
        with c2: criar_barra("🔴 Perdendo", p_perd, "#dc3545")
        with c3: criar_barra("⚪ Ruptura", p_rupt, "#6c757d") # Corrigido c3 aqui

        st.divider()
        st.caption(f"🕒 Atualizado em: {hist[0]['data']}")
        
        # Reorganizar e configurar tabela limpa
        ordem = ["Produto", "Vidafarma", "L_Vidafarma", "Cremer", "L_Cremer", "Speed", "L_Speed", "Surya", "L_Surya"]
        df = df[ordem]
        
        st.dataframe(
            df.set_index("Produto"),
            use_container_width=True,
            column_config={
                "L_Vidafarma": st.column_config.LinkColumn("", display_text="🔗", width="small"),
                "L_Cremer": st.column_config.LinkColumn("", display_text="🔗", width="small"),
                "L_Speed": st.column_config.LinkColumn("", display_text="🔗", width="small"),
                "L_Surya": st.column_config.LinkColumn("", display_text="🔗", width="small"),
            }
        )
