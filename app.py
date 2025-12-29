with aba_dash:
    historico = carregar_json(HIST_FILE)
    
    col_t1, col_t2 = st.columns([3, 1])
    col_t1.subheader("📊 Painel de Performance")
    
    if st.button("🚀 ATUALIZAR PREÇOS AGORA"):
        # ... (seu código de acionamento dos robôs que já temos)
        lista_prods = carregar_json(DB_FILE)
        if lista_prods:
            tarefas = []
            for p in lista_prods:
                tarefas.append({"id": p['nome'], "loja": "Vidafarma (MEU)", "url": p['vidafarma'], "seletor": ".customProduct__price"})
                tarefas.append({"id": p['nome'], "loja": "Cremer", "url": p['cremer'], "seletor": ".price"})
                tarefas.append({"id": p['nome'], "loja": "Speed", "url": p['speed'], "seletor": "[data-price-type='finalPrice']"})
                tarefas.append({"id": p['nome'], "loja": "Surya", "url": p['surya'], "seletor": ".priceProduct-productPrice-2XFbc"})

            with st.status("Robôs trabalhando...", expanded=True):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    res_brutos = list(executor.map(capturar_loja, tarefas))
                matriz = {}
                for i, t in enumerate(tarefas):
                    if t['id'] not in matriz: matriz[t['id']] = {"Produto": t['id']}
                    matriz[t['id']][t['loja']] = res_brutos[i]['valor']
                final_dados = list(matriz.values())
                salvar_json(HIST_FILE, [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "dados": final_dados}])
                st.rerun()

    if historico:
        df = pd.DataFrame(historico[0]['dados'])
        
        # --- LÓGICA DE CÁLCULO ---
        def extrair_v(texto):
            try:
                num = re.search(r'R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', str(texto))
                return float(num.group(1).replace('.', '').replace(',', '.')) if num else None
            except: return None

        total = len(df)
        ganhando, perdendo, ruptura = 0, 0, 0

        for _, row in df.iterrows():
            meu_p = extrair_v(row['Vidafarma (MEU)'])
            if "❌" in str(row['Vidafarma (MEU)']): ruptura += 1
            
            concs = [extrair_v(row[c]) for c in ['Cremer', 'Speed', 'Surya'] if extrair_v(row[c])]
            if meu_p and concs:
                if meu_p < min(concs): ganhando += 1
                elif meu_p > min(concs): perdendo += 1

        p_ganhando = (ganhando / total) * 100 if total > 0 else 0
        p_perdendo = (perdendo / total) * 100 if total > 0 else 0
        p_ruptura = (ruptura / total) * 100 if total > 0 else 0

        # --- FUNÇÃO PARA CRIAR A BARRA HORIZONTAL ---
        def criar_barra(label, percent, cor):
            st.markdown(f"""
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-weight: bold; font-size: 14px;">{label}</span>
                        <span style="font-weight: bold; font-size: 14px;">{percent:.1f}%</span>
                    </div>
                    <div style="background-color: #e0e0e0; border-radius: 10px; width: 100%; height: 18px;">
                        <div style="background-color: {cor}; width: {percent}%; height: 100%; border-radius: 10px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # --- EXIBIÇÃO DAS BARRAS ---
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            criar_barra("🔥 Ganhando", p_ganhando, "#28a745") # Verde
        with col_b2:
            criar_barra("⚠️ Perdendo", p_perdendo, "#dc3545") # Vermelho
        with col_b3:
            criar_barra("📦 Ruptura (Sem Estoque)", p_ruptura, "#6c757d") # Cinza

        st.divider()
        st.caption(f"🕒 Dados de: {historico[0]['data']}")
        st.dataframe(df.set_index("Produto"), use_container_width=True)
