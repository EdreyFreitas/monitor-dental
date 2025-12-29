import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import re
import json
import os
import subprocess
from datetime import datetime

# --- CONFIGURAÇÃO SaaS PREMIUM ---
st.set_page_config(page_title="Dental Intel Flash", page_icon="⚡", layout="wide")

# CSS para Visual SaaS Vendável
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; border-top: 4px solid #007BFF; }
    .product-header { background: #21262d; padding: 10px 20px; border-radius: 8px 8px 0 0; margin-top: 25px; color: #58a6ff; font-weight: 700; font-size: 18px; border: 1px solid #30363d; }
    .shop-card { background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; transition: 0.2s; height: 100%; border-top: 3px solid #333; }
    .price-val { font-size: 26px; font-weight: 800; color: #fff; margin: 10px 0; }
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

# --- MOTOR ULTRA-FAST (PLAYWRIGHT) ---
async def scrape_site(context, url, loja):
    if not url: return {"preco": 0.0, "estoque": "Sem URL", "url": ""}
    page = await context.new_page()
    
    # ACELERAÇÃO SaaS: Bloqueia imagens, fontes e analytics
    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,ttf,css}", lambda route: route.abort())
    
    try:
        # Abre o site e espera apenas o "mínimo" para ler o texto
        await page.goto(url, wait_until="commit", timeout=15000)
        
        # Seletores
        if "vidafarma" in url: s = ".customProduct__price"
        elif "surya" in url: s = "p[class*='priceProduct-productPrice']"
        elif "speed" in url: s = "[data-price-type='finalPrice']"
        else: s = ".price"
        
        await page.wait_for_selector(s, timeout=8000)
        texto = await page.inner_text(s)
        
        # Lógica de Preço Blindada
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums if float(n.replace('.', '').replace(',', '.')) > 1.0]
        preco = max(valores) if "vidafarma" in url else min(valores)
        
        # Estoque Simplificado por Botão
        content = (await page.content()).lower()
        estoque = "✅ DISPONÍVEL" if "adicionar" in content or "comprar" in content else "❌ ESGOTADO"
        
        return {"preco": preco, "estoque": estoque, "url": url}
    except:
        return {"preco": 0.0, "estoque": "ERRO", "url": url}
    finally:
        await page.close()

async def run_turbo_sync():
    # Garante que o Playwright está instalado no servidor
    subprocess.run(["playwright", "install", "chromium"])
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        final_results = []
        for p_item in PRODUTOS_FIXOS:
            # DISPARA TODAS AS LOJAS DO PRODUTO AO MESMO TEMPO (Paralelismo Total)
            tasks = [
                scrape_site(context, p_item['vidafarma'], "Vidafarma"),
                scrape_site(context, p_item['cremer'], "Cremer"),
                scrape_site(context, p_item['speed'], "Speed"),
                scrape_site(context, p_item['surya'], "Surya")
            ]
            res_lojas = await asyncio.gather(*tasks)
            
            final_results.append({
                "nome": p_item['nome'],
                "lojas": {
                    "Vidafarma": res_lojas[0], "Cremer": res_lojas[1], 
                    "Speed": res_lojas[2], "Surya": res_lojas[3]
                }
            })
        await browser.close()
        return final_results

# --- INTERFACE SaaS ---
st.title("⚡ Dental Intelligence SaaS")

if st.button("🚀 SINCRONIZAÇÃO FLASH (Sub-10s)", use_container_width=True):
    with st.spinner("Motor Playwright em alta velocidade..."):
        results = asyncio.run(run_turbo_sync())
        hist_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": results}
        with open(HIST_FILE, "w") as f: json.dump(hist_data, f)
        st.rerun()

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r") as f: hist = json.load(f)
    
    # KPIs Rápidos
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
                st.markdown(f"""
                <div class="shop-card" style="border-top-color: {cor};">
                    <div style="color:#888; font-size:11px; font-weight:600;">{loja.upper()}</div>
                    <div class="price-val">{p_txt}</div>
                    <div style="margin-top:10px;"><span style="background:{st_bg}; padding:3px 8px; border-radius:10px; font-size:10px; color:white;">{info['estoque']}</span></div>
                    <div style="margin-top:12px;"><a href="{info['url']}" target="_blank" style="color:#58a6ff; font-size:12px; text-decoration:none;">Conferir ↗️</a></div>
                </div>
                """, unsafe_allow_html=True)
