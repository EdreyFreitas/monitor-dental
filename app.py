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
st.set_page_config(page_title="Monitor Dental Turbo", page_icon="⚡", layout="wide")

DB_FILE = "produtos.json"
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
    if not url or url == "": return {"loja": loja, "valor": "N/A"}
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
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
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor)))
        time.sleep(2)
        elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
        precos_encontrados = []
        for el in elementos:
            texto = el.text.replace(' ', '').replace('\xa0', '').replace('\n', '')
            matches = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
            for m in matches:
