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
st.set_page_config(page_title="Monitor Dental Curva A", page_icon="🦷", layout="wide")

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
    url = tarefa['url']
    seletor = tarefa['seletor']
    loja = tarefa['loja']
    if not url or url == "": return {"loja": loja, "valor": "N/A", "url": ""}
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,720")
    prefs = {"profile.managed_default_content_settings.images": 2}
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except:
        driver = webdriver.Chrome(options=opts)
    
    try:
        driver.get(url)
        tempo_espera = 20 if "surya" in url.lower() else 15
        css = "p[class*='priceProduct-productPrice']" if "surya" in url.lower() else seletor
        WebDriverWait(driver, tempo_espera).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
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
    st.subheader("Produtos Extras")
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
        col1, col2 = st.columns([5,1])
        col1.write(f"📦 {p['nome']}")
        if col2.button("Remover", key=f"del_{i}"):
            ex = carregar_json(DB_FILE); ex.pop(i); salvar_json(DB_FILE, ex); st.rerun()

with aba_dash:
    hist = carregar_json(HIST_FILE)
    
    if st.button("🚀 ATUALIZAR TUDO"):
        todos = PRODUTOS_FIXOS + carregar_json(DB_FILE)
        if todos:
            tarefas = []
            for p in todos:
                tarefas.append({"id": p['nome'], "loja": "Vidafarma", "url": p['vidafarma'], "seletor": ".customProduct__price"})
                tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
                tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
                tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

            with st.status("Varredura em andamento...", expanded=True):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    brutos = list(executor.map(capturar_loja, tarefas))
                
                matriz = {}
                for i, t in enumerate(tarefas):
                    pid = t['id']
                    if pid not in matriz: matriz[pid] = {"Produto": pid}
                    # Preço e Link em colunas separadas para formatação
                    matriz[pid][t['loja']] = brutos[i]['valor']
                    matriz[pid][f"L_{t['loja']}"] = brutos[i]['url']
                
                salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": list(matriz.values())}])
                st.rerun()

    if hist:
        df = pd.DataFrame(hist[0]['dados'])
        
        # --- REORGANIZAR COLUNAS PARA FICAR PREÇO | LINK ---
        ordem_colunas = ["Produto", 
                         "Vidafarma", "L_Vidafarma", 
                         "Cremer", "L_Cremer", 
                         "Speed", "L_Speed", 
                         "Surya", "L_Surya"]
        df = df[ordem_colunas]
        
        # (Código dos cálculos de dashboard omitido aqui para focar na tabela, mas mantenha o seu)

        st.divider()
        st.caption(f"🕒 Última atualização: {hist[0]['data']}")
        
        # --- TABELA ESTILIZADA ---
        st.dataframe(
            df.set_index("Produto"),
            use_container_width=True,
            column_config={
                # Colunas de Preço (Configuração padrão)
                "Vidafarma": st.column_config.Column("Vidafarma", width="medium"),
                "Cremer": st.column_config.Column("Cremer", width="medium"),
                "Speed": st.column_config.Column("Speed", width="medium"),
                "Surya": st.column_config.Column("Surya", width="medium"),
                
                # Colunas de Link (Configuradas como ícones pequenos)
                "L_Vidafarma": st.column_config.LinkColumn("🔗", display_text="↗️", width="small"),
                "L_Cremer": st.column_config.LinkColumn("🔗", display_text="↗️", width="small"),
                "L_Speed": st.column_config.LinkColumn("🔗", display_text="↗️", width="small"),
                "L_Surya": st.column_config.LinkColumn("🔗", display_text="↗️", width="small"),
            }
        )
    else:
        st.warning("Clique em 'Atualizar' para começar.")

    if hist:
        df = pd.DataFrame(hist[0]['dados'])
        
        # --- CÁLCULOS DASHBOARD ---
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
        
        st.subheader("📊 Indicadores")
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 Ganhando", f"{(ganhando/total)*100 if total>0 else 0:.1f}%")
        c2.metric("⚠️ Perdendo", f"{(perdendo/total)*100 if total>0 else 0:.1f}%")
        c3.metric("📦 Ruptura", f"{(ruptura/total)*100 if total>0 else 0:.1f}%")

        st.divider()
        st.caption(f"Dados de: {hist[0]['data']}")
        
        # --- TABELA COM LINKS CLICÁVEIS ---
        # Configuramos as colunas que começam com "🔗" para serem links
        st.dataframe(
            df.set_index("Produto"),
            use_container_width=True,
            column_config={
                "🔗 Vidafarma": st.column_config.LinkColumn("🔗 Vida", display_text="Abrir"),
                "🔗 Cremer": st.column_config.LinkColumn("🔗 Cremer", display_text="Abrir"),
                "🔗 Speed": st.column_config.LinkColumn("🔗 Speed", display_text="Abrir"),
                "🔗 Surya": st.column_config.LinkColumn("🔗 Surya", display_text="Abrir"),
            }
        )
    else:
        st.warning("Clique em 'Atualizar' para começar.")
