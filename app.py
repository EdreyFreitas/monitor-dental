import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import re
import json
import os
from datetime import datetime

# --- CONFIGURAÇÃO SaaS DARK ---
st.set_page_config(page_title="Dental Intel Pro", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0e1117; }
    .kpi-card { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; text-align: center; }
    .product-title { background: #21262d; padding: 12px 20px; border-radius: 8px 8px 0 0; border-left: 5px solid #007BFF; margin-top: 25px; color: #58a6ff; font-weight: 700; font-size: 18px; }
    .shop-card { background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; transition: 0.2s; height: 100%; border-top: 3px solid #333; }
    .shop-card:hover { border-color: #007BFF; background: #121d2f; }
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

# --- MOTOR ULTRA RÁPIDO (PLAYWRIGHT ASYNC) ---
async def fetch_price(context, url, loja):
    if not url: return {"preco": 0.0, "estoque": "N/A", "url": ""}
    page = await context.new_page()
    # Bloqueia imagens e CSS para voar no carregamento
    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        
        # Seletores
        if "vidafarma" in url: selector = ".customProduct__price"
        elif "surya" in url: selector = "p[class*='priceProduct-productPrice']"
        elif "speed" in url: selector = "[data-price-type='finalPrice']"
        else: selector = ".price"

        await page.wait_for_selector(selector, timeout=10000)
        texto = await page.inner_text(selector)
        
        # Limpeza e extração
        nums = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        valores = [float(n.replace('.', '').replace(',', '.')) for n in nums]
        
        preco = max(valores) if "vidafarma" in url else min(valores)
        
        content = (await page.content()).lower()
        estoque = "✅ DISPONÍVEL" if "adicionar" in content or "comprar" in content else "❌ ESGOTADO"
        
        return {"preco": preco, "estoque": estoque, "url": url}
    except:
        return {"preco": 0.0, "estoque": "ERRO", "url": url}
    finally:
        await page.close()

async def run_sync():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        all_results = []
        for p_item in PRODUTOS_FIXOS:
            # DISPARA TODAS AS LOJAS DO PRODUTO AO MESMO TEMPO
            tasks = [
                fetch_price(context, p_item['vidafarma'], "Vidafarma"),
                fetch_price(context, p_item['cremer'], "Cremer"),
                fetch_price(context, p_item['speed'], "Speed"),
                fetch_price(context, p_item['surya'], "Surya")
            ]
            res_lojas = await asyncio.gather(*tasks)
            
            all_results.append({
                "nome": p_item['nome'],
                "lojas": {
                    "Vidafarma": res_lojas[0],
                    "Cremer": res_lojas[1],
                    "Speed": res_lojas[2],
                    "Surya": res_lojas[3]
                }
            })
        await browser.close()
        return all_results

# --- INTERFACE ---
st.title("⚡ Dental Market Intelligence Pro")

if st.button("🚀 SINCRONIZAÇÃO INSTANTÂNEA", use_container_width=True):
    with st.spinner("Robôs Playwright em campo (Alta Velocidade)..."):
        # Executa o motor assíncrono
        data_list = asyncio.run(run_sync())
        hist_data = {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "produtos": data_list}
        with open(HIST_FILE, "w") as f: json.dump(hist_data, f)
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
    c1.markdown(f'<div class="kpi-card" style="border-left-color:#28a745"><div style="color:#888;font-size:11px">GANHANDO</div><div style="font-size:26px;font-weight:700">{ganhando}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card" style="border-left-color:#ffc107"><div style="color:#888;font-size:11px">EMPATADOS</div><div style="font-size:26px;font-weight:700">{empatados}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card" style="border-left-color:#dc3545"><div style="color:#888;font-size:11px">PERDENDO</div><div style="font-size:26px;font-weight:700">{perdendo}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card" style="border-left-color:#6c757d"><div style="color:#888;font-size:11px">RUPTURA</div><div style="font-size:26px;font-weight:700">{ruptura}</div></div>', unsafe_allow_html=True)
    
    st.divider()

    for p in hist['produtos']:
        st.markdown(f'<div class="product-title">{p["nome"]}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        lojas_ordem = ["Vidafarma", "Cremer", "Speed", "Surya"]
        for i, nome_loja in enumerate(lojas_ordem):
            info = p['lojas'][nome_loja]
            with cols[i]:
                cor_top = "#007BFF" if nome_loja == "Vidafarma" else "#333"
                preco_f = f"R$ {info['preco']:,.2f}".replace('.',',') if info['preco'] > 0 else "---"
                st_bg = "#238636" if "✅" in info['estoque'] else "#da3633"
                if info['estoque'] == "ERRO": st_bg = "#555"
                
                st.markdown(f"""
                <div class="shop-card" style="border-top-color: {cor_top};">
                    <div style="color:#888; font-size:11px; font-weight:600;">{nome_loja}</div>
                    <div class="price-val">{preco_f}</div>
                    <div style="margin-top:10px;"><span class="status-badge" style="background:{st_bg}">{info['estoque']}</span></div>
                    <div style="margin-top:12px;"><a href="{info['url']}" target="_blank" style="color:#58a6ff; font-size:12px; text-decoration:none;">Conferir ↗️</a></div>
                </div>
                """, unsafe_allow_html=True)
