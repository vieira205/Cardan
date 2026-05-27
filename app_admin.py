import sqlite3
import gradio as gr
import pandas as pd
import hashlib
import uuid
import os
import qrcode

DIRETORIO = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(DIRETORIO, "pratos.db")

# -----------------------------
# 1. FUNÇÕES DE BANCO E SEGURANÇA
# -----------------------------
def inicializar_banco():
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN numero_mesa TEXT DEFAULT 'Balcão'")
    except: pass
    
    try: cursor.execute("ALTER TABLE pratos ADD COLUMN preco_promocional REAL")
    except: pass


    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            password_cozinha TEXT NOT NULL,
            id_restaurante TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            foto TEXT,
            id_restaurante TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente',
            id_restaurante TEXT,
            numero_mesa TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingredientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            status TEXT DEFAULT 'Disponível',
            id_restaurante TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prato_ingredientes (
            id_prato INTEGER,
            id_ingrediente INTEGER,
            PRIMARY KEY (id_prato, id_ingrediente)
        )
    ''')
    conn.commit()
    conn.close()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def registrar_usuario(usuario, senha_admin, senha_cozinha):
    if not usuario or not senha_admin or not senha_cozinha:
        return "Erro: Preencha o usuário e as duas senhas."
    
    # ---> A TRAVA DE SEGURANÇA AQUI <---
    if senha_admin == senha_cozinha:
        return "Erro: A senha da Cozinha não pode ser igual à do Administrador."
    
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    try:
        id_restaurante = str(uuid.uuid4().hex)[:8]
        cursor.execute("INSERT INTO usuarios (username, password, password_cozinha, id_restaurante) VALUES (?, ?, ?, ?)", 
                       (usuario, hash_senha(senha_admin), hash_senha(senha_cozinha), id_restaurante))
        conn.commit()
        msg = f"Conta criada! Seu ID de Restaurante é: {id_restaurante}. Faça login."
    except sqlite3.IntegrityError:
        msg = "Erro: Nome de usuário já existe."
    finally:
        conn.close()
    
    return msg

def validar_login(usuario, senha_digitada):
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("SELECT id_restaurante, password, password_cozinha FROM usuarios WHERE username = ?", (usuario,))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        id_restaurante, pass_admin, pass_cozinha = resultado
        senha_hash = hash_senha(senha_digitada)
        
        # Checa se a senha bate com a do ADMIN
        if senha_hash == pass_admin:
            return id_restaurante, "admin", gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), f"👨‍💼 Bem-vindo Admin! (ID: {id_restaurante})"
        
        # Checa se a senha bate com a da COZINHA
        elif senha_hash == pass_cozinha:
            return id_restaurante, "cozinha", gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), f"👨‍🍳 Bem-vinda Cozinha! (ID: {id_restaurante})"
            
    return None, None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), "❌ Usuário ou senha incorretos."

def fazer_logout():
    # Esconde os dois painéis e mostra o login novamente
    return None, None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)

# -----------------------------
# 2. FUNÇÕES DE PEDIDOS E CAIXA
# -----------------------------
def listar_pedidos(id_rest):
    if not id_rest: return pd.DataFrame()
    conn = sqlite3.connect(BANCO)
    df = pd.read_sql_query("SELECT id, numero_mesa as 'Mesa', descricao, data_hora, status FROM pedidos WHERE id_restaurante = ? ORDER BY id DESC", conn, params=(id_rest,))
    conn.close()
    return df

def atualizar_status_pedido(id_pedido, novo_status, id_rest):
    if not id_pedido or not novo_status:
        return "Erro: Informe o ID do pedido e o novo status.", listar_pedidos(id_rest)
    
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    
    if novo_status in ["Entregue/Finalizado", "Cancelado"]:
        cursor.execute("DELETE FROM pedidos WHERE id = ? AND id_restaurante = ?", (id_pedido, id_rest))
        acao_realizada = f"removido da fila ({novo_status})"
    else:
        cursor.execute("UPDATE pedidos SET status = ? WHERE id = ? AND id_restaurante = ?", (novo_status, id_pedido, id_rest))
        acao_realizada = f"atualizado para '{novo_status}'"
        
    linhas = cursor.rowcount
    conn.commit()
    conn.close()
    
    if linhas > 0:
        return f"Pedido #{id_pedido} {acao_realizada}!", listar_pedidos(id_rest)
    return "Erro: Pedido não encontrado ou não pertence a este restaurante.", listar_pedidos(id_rest)

def calcular_conta_mesa(mesa, id_rest):
    if not id_rest or not mesa:
        return "Informe o número da mesa", pd.DataFrame(columns=["Qtd", "Item", "Preço Unit.", "Subtotal"])
    
    conn = sqlite3.connect(BANCO)
    
    # 1. Pega os preços normais E promocionais
    df_pratos = pd.read_sql_query("SELECT nome, preco, preco_promocional FROM pratos WHERE id_restaurante = ?", conn, params=(id_rest,))
    
    tabela_precos = {}
    for _, row in df_pratos.iterrows():
        preco_normal = row['preco']
        preco_promo = row['preco_promocional']
        if pd.notna(preco_promo) and preco_promo > 0:
            tabela_precos[row['nome']] = preco_promo
        else:
            tabela_precos[row['nome']] = preco_normal
            
    # 2. Pega todos os pedidos ativos dessa mesa
    df_pedidos = pd.read_sql_query("SELECT id, descricao FROM pedidos WHERE id_restaurante = ? AND numero_mesa = ?", conn, params=(id_rest, str(mesa)))
    
    if df_pedidos.empty:
        conn.close()
        return f"Nenhum pedido pendente para a Mesa {mesa}.", pd.DataFrame(columns=["Qtd", "Item", "Preço Unit.", "Subtotal"])
    
    linhas_conta = []
    total_geral = 0.0
    
    # 3. Lê o texto do pedido e calcula
    for _, row in df_pedidos.iterrows():
        descricao = row['descricao']
        itens = [i.strip() for i in descricao.split("  +  ")]
        
        for item in itens:
            if "x " in item:
                try:
                    qtd_str, nome_prato = item.split("x ", 1)
                    qtd = int(qtd_str)
                    
                    preco_unit = tabela_precos.get(nome_prato, 0.0) 
                    subtotal = qtd * preco_unit
                    total_geral += subtotal
                    
                    linhas_conta.append({
                        "Qtd": qtd,
                        "Item": nome_prato,
                        "Preço Unit.": f"R$ {preco_unit:.2f}",
                        "Subtotal": f"R$ {subtotal:.2f}"
                    })
                except:
                    pass

    # 4. Muda o status de todos os pedidos da mesa para "Aguardando Pagamento"
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET status = 'Aguardando Pagamento' WHERE id_restaurante = ? AND numero_mesa = ?", (id_rest, str(mesa)))
    conn.commit()
    conn.close()
    
    df_conta = pd.DataFrame(linhas_conta)
    return f"### Total da Mesa {mesa}: R$ {total_geral:.2f}", df_conta
            

def finalizar_conta_mesa(mesa, id_rest):
    if not id_rest or not mesa: return "Informe a mesa"
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pedidos WHERE id_restaurante = ? AND numero_mesa = ?", (id_rest, str(mesa)))
    linhas = cursor.rowcount
    conn.commit()
    conn.close()
    if linhas > 0: return f"Conta da Mesa {mesa} fechada! Pedidos finalizados."
    return "Nenhum pedido encontrado para fechar."

def ao_clicar_na_tabela(evt: gr.SelectData, df_pedidos):
    linha = evt.index[0]
    id_selecionado = int(df_pedidos.iloc[linha]['id'])
    status_atual = df_pedidos.iloc[linha]['status']
    return id_selecionado, status_atual

# -----------------------------
# 3. LÓGICA DE INGREDIENTES E QR CODE
# -----------------------------
def gr_listar_ingredientes(id_rest):
    if not id_rest: return pd.DataFrame()
    conn = sqlite3.connect(BANCO)
    df = pd.read_sql_query("SELECT id, nome, status FROM ingredientes WHERE id_restaurante = ?", conn, params=(id_rest,))
    conn.close()
    return df

def gr_adicionar_ingrediente(nome, status, id_rest):
    if not nome: return "Erro: Nome do ingrediente é obrigatório", gr_listar_ingredientes(id_rest)
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ingredientes (nome, status, id_restaurante) VALUES (?, ?, ?)", (nome, status, id_rest))
    conn.commit()
    conn.close()
    return f"Ingrediente '{nome}' adicionado!", gr_listar_ingredientes(id_rest)

def gr_alterar_status_ingrediente(id_ing, novo_status, id_rest):
    if not id_ing: return "Erro: ID necessário", gr_listar_ingredientes(id_rest)
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("UPDATE ingredientes SET status = ? WHERE id = ? AND id_restaurante = ?", (novo_status, int(id_ing), id_rest))
    conn.commit()
    conn.close()
    return f"Status do ingrediente ID {id_ing} modificado para {novo_status}!", gr_listar_ingredientes(id_rest)

def gerar_qr_code(numero_mesa, link_base, id_rest):
    if not id_rest: return None
    url_base = link_base.strip() if link_base and link_base.strip() != "" else "http://localhost:7860"
    
    if numero_mesa and numero_mesa > 0:
        url_final = f"{url_base}/?rest={id_rest}&mesa={int(numero_mesa)}"
    else:
        url_final = f"{url_base}/?rest={id_rest}"
        
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url_final)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").get_image()

# -----------------------------
# 4. CRUD DE PRATOS 
# -----------------------------
def gr_listar(id_rest):
    if not id_rest: return pd.DataFrame()
    conn = sqlite3.connect(BANCO)
    query = '''
        SELECT DISTINCT p.id, p.nome, p.preco, p.preco_promocional as 'Promoção', p.foto 
        FROM pratos p
        WHERE p.id_restaurante = ?
        AND p.id NOT IN (
            SELECT pi.id_prato 
            FROM prato_ingredientes pi
            JOIN ingredientes i ON pi.id_ingrediente = i.id
            WHERE i.status = 'Esgotado'
        )
    '''
    df = pd.read_sql_query(query, conn, params=(id_rest,))
    conn.close()

    if not df.empty:
        df['foto'] = df['foto'].apply(lambda x: f'<img src="{x}" width="50" height="50" style="border-radius: 5px;">' if pd.notna(x) and x != "" else "Sem foto")
    return df

def gr_criar(nome, preco, preco_promo, foto, ids_ingredientes_str, id_rest):
    if not nome or not preco: return "Erro: Nome e Preço são obrigatórios", gr_listar(id_rest)
    preco_promo_val = float(preco_promo) if preco_promo else None
    
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pratos (nome, preco, preco_promocional, foto, id_restaurante) VALUES (?, ?, ?, ?, ?)', 
                   (nome, float(preco), preco_promo_val, foto, id_rest))
    id_prato_criado = cursor.lastrowid

    if ids_ingredientes_str:
        try:
            ids_ingredientes = [int(x.strip()) for x in ids_ingredientes_str.split(",") if x.strip().isdigit()]
            for id_ing in ids_ingredientes:
                cursor.execute('INSERT OR IGNORE INTO prato_ingredientes (id_prato, id_ingrediente) VALUES (?, ?)', (id_prato_criado, id_ing))
        except Exception: pass
    conn.commit()
    conn.close()
    return f"Prato '{nome}' criado com sucesso!", gr_listar(id_rest)

def gr_excluir(id_busca, id_rest):
    if not id_busca: return "Erro: Forneça o ID", gr_listar(id_rest)
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pratos WHERE id = ? AND id_restaurante = ?", (id_busca, id_rest))
    cursor.execute("DELETE FROM prato_ingredientes WHERE id_prato = ?", (id_busca,))
    linhas_afetadas = cursor.rowcount
    conn.commit()
    conn.close()
    if linhas_afetadas > 0: return f"Prato ID {id_busca} removido!", gr_listar(id_rest)
    return "Erro: ID não encontrado", gr_listar(id_rest)

def gr_editar(id_busca, nome, preco, preco_promo, foto, id_rest):
    if not id_busca: return "Erro: Forneça o ID do prato", gr_listar(id_rest)
    campos, valores = [], []
    if nome: campos.append("nome = ?"); valores.append(nome)
    if preco: campos.append("preco = ?"); valores.append(float(preco))
    if foto: campos.append("foto = ?"); valores.append(foto)
    
    if preco_promo is not None and str(preco_promo).strip() != "":
        campos.append("preco_promocional = ?")
        valores.append(float(preco_promo) if float(preco_promo) > 0 else None)

    if not campos: return "Nenhum dado informado", gr_listar(id_rest)

    valores.extend([id_busca, id_rest])
    query = f"UPDATE pratos SET {', '.join(campos)} WHERE id = ? AND id_restaurante = ?"
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute(query, tuple(valores))
    linhas_afetadas = cursor.rowcount
    conn.commit()
    conn.close()
    if linhas_afetadas > 0: return f"Prato ID {id_busca} atualizado!", gr_listar(id_rest)
    return "Erro: Prato não encontrado", gr_listar(id_rest)

# -----------------------------
# 5. INTERFACE GRADIO
# -----------------------------
inicializar_banco()

with gr.Blocks(title="Gestão de Restaurante") as demo:
    sessao_usuario = gr.State(None)
    sessao_perfil = gr.State(None) # Guarda se é "admin" ou "cozinha"

    # ==========================================
    # TELA DE LOGIN E REGISTRO
    # ==========================================
    with gr.Column(visible=True) as tela_login:
        gr.Markdown("# Acesso ao Sistema CARD🍔N")
        
        with gr.Tab("Login"):
            login_user = gr.Textbox(label="Usuário")
            login_senha = gr.Textbox(label="Senha (Admin ou Cozinha)", type="password")
            btn_login = gr.Button("Entrar", variant="primary")
            msg_login = gr.Markdown("")
            
        with gr.Tab("Registrar Novo Restaurante"):
            reg_user = gr.Textbox(label="Novo Usuário (Para o restaurante)")
            reg_senha_admin = gr.Textbox(label="Senha do Administrador (Acesso Completo)", type="password")
            reg_senha_cozinha = gr.Textbox(label="Senha da Cozinha (Acesso a Pedidos e Caixa)", type="password")
            btn_registrar = gr.Button("Registrar Restaurante")
            msg_reg = gr.Markdown("")
            btn_registrar.click(registrar_usuario, inputs=[reg_user, reg_senha_admin, reg_senha_cozinha], outputs=[msg_reg])

    # ==========================================
    # PAINEL DA COZINHA (Apenas Pedidos, Caixa e Visualização)
    # ==========================================
    with gr.Column(visible=False) as tela_cozinha:
        with gr.Row():
            titulo_cozinha = gr.Markdown("# CARD🍔N - Painel da Cozinha e Caixa")
            btn_logout_coz = gr.Button("Sair", size="sm")

        with gr.Tabs():
            # ABA 1: Cozinha
            with gr.TabItem("Fila de Pedidos"):
                tabela_pedidos = gr.Dataframe(label="Pedidos Recebidos", interactive=False)
                timer_pedidos = gr.Timer(5)
                timer_pedidos.tick(fn=listar_pedidos, inputs=[sessao_usuario], outputs=tabela_pedidos)

                gr.Markdown("### Atualizar Status do Pedido")
                with gr.Row():
                    in_id_pedido = gr.Number(label="ID do Pedido", precision=0, interactive=False)
                    in_status_pedido = gr.Dropdown(choices=["Pendente", "Preparando", "Pronto para Retirada", "Aguardando Pagamento", "Entregue/Finalizado", "Cancelado"], label="Novo Status")
                    btn_status = gr.Button("Confirmar Mudança", variant="primary")
                
                out_msg_status = gr.Textbox(label="Status da Operação")
                
                tabela_pedidos.select(fn=ao_clicar_na_tabela, inputs=[tabela_pedidos], outputs=[in_id_pedido, in_status_pedido])
                btn_status.click(fn=atualizar_status_pedido, inputs=[in_id_pedido, in_status_pedido, sessao_usuario], outputs=[out_msg_status, tabela_pedidos])

            # ABA 2: Fechamento de Conta
            with gr.TabItem("Caixa / Fechar Conta"):
                gr.Markdown("### Fechamento de Mesa")
                with gr.Row():
                    in_mesa_conta = gr.Textbox(label="Número da Mesa ou 'Balcão'")
                    btn_calc_conta = gr.Button("Calcular Conta", variant="primary")
                
                out_total = gr.Markdown("### Total: R$ 0.00")
                out_tabela_conta = gr.Dataframe(label="Detalhes do Consumo", interactive=False)
                
                with gr.Row():
                    btn_pagar = gr.Button("Confirmar Pagamento e Liberar Mesa", variant="stop")
                    out_msg_pagar = gr.Textbox(label="Status")

                btn_calc_conta.click(fn=calcular_conta_mesa, inputs=[in_mesa_conta, sessao_usuario], outputs=[out_total, out_tabela_conta]).then(fn=listar_pedidos, inputs=[sessao_usuario], outputs=[tabela_pedidos])
                btn_pagar.click(fn=finalizar_conta_mesa, inputs=[in_mesa_conta, sessao_usuario], outputs=[out_msg_pagar]).then(fn=listar_pedidos, inputs=[sessao_usuario], outputs=[tabela_pedidos])

            # ABA 3: Lista de Pratos
            with gr.TabItem("Ver Cardápio Ativo"):
                btn_refresh_coz = gr.Button("Atualizar Catálogo")
                output_table_cozinha = gr.Dataframe(label="Cardápio Atual", datatype=["number", "str", "number", "html"], wrap=True, interactive=False)
                btn_refresh_coz.click(fn=gr_listar, inputs=[sessao_usuario], outputs=output_table_cozinha)

    # ==========================================
    # PAINEL DE ADMINISTRAÇÃO
    # ==========================================
    with gr.Column(visible=False) as tela_admin:
        with gr.Row():
            titulo_admin = gr.Markdown("# CARD🍔N - Administração")
            btn_logout_admin = gr.Button("Sair", size="sm")

        with gr.Tabs():
            # ABA 1: Lista de Pratos (Gestão)
            with gr.TabItem("Catálogo de Pratos Ativos"):
                btn_refresh_adm = gr.Button("Atualizar Catálogo")
                output_table_admin = gr.Dataframe(label="Cardápio Ativo", datatype=["number", "str", "number", "number", "html"], wrap=True)
                btn_refresh_adm.click(fn=gr_listar, inputs=[sessao_usuario], outputs=output_table_admin)
                
            # ABA 2: Ingredientes
            with gr.TabItem("Gestão de Ingredientes"):
                tabela_ingredientes = gr.Dataframe(label="Seus Ingredientes em Estoque", interactive=False)
                btn_refresh_ing = gr.Button("Atualizar Lista de Estoque")
                btn_refresh_ing.click(fn=gr_listar_ingredientes, inputs=[sessao_usuario], outputs=tabela_ingredientes)
                
                with gr.Row():
                    with gr.Group():
                        gr.Markdown("### Adicionar Novo Ingrediente")
                        in_ing_nome = gr.Textbox(label="Nome (Ex: Queijo Cheddar)")
                        in_ing_status = gr.Dropdown(choices=["Disponível", "Esgotado"], value="Disponível", label="Status Inicial")
                        btn_add_ing = gr.Button("Cadastrar Ingrediente")
                    with gr.Group():
                        gr.Markdown("### Alterar Disponibilidade")
                        in_ing_id = gr.Textbox(label="ID do Ingrediente")
                        in_ing_novo_status = gr.Dropdown(choices=["Disponível", "Esgotado"], label="Mudar para")
                        btn_status_ing = gr.Button("Atualizar Estoque", variant="primary")
                
                out_msg_ing = gr.Textbox(label="Resultado da Ação")
                btn_add_ing.click(gr_adicionar_ingrediente, [in_ing_nome, in_ing_status, sessao_usuario], [out_msg_ing, tabela_ingredientes])
                btn_status_ing.click(gr_alterar_status_ingrediente, [in_ing_id, in_ing_novo_status, sessao_usuario], [out_msg_ing, tabela_ingredientes])

            # ABA 3: Cadastrar Pratos
            with gr.TabItem("Cadastrar Novo Prato"):
                with gr.Row():
                    in_nome = gr.Textbox(label="Nome do Prato")
                    in_preco = gr.Number(label="Preço Normal (R$)")
                    in_preco_promo = gr.Number(label="Preço Promocional (Opcional - R$)") # NOVO
                in_foto = gr.Textbox(label="URL da Foto")
                in_prato_ings = gr.Textbox(label="IDs dos Ingredientes (ex: 1, 4, 7)")
                btn_create = gr.Button("Salvar Prato", variant="primary")
                out_msg_create = gr.Textbox(label="Status")
                btn_create.click(gr_criar, [in_nome, in_preco, in_preco_promo, in_foto, in_prato_ings, sessao_usuario], [out_msg_create, output_table_admin])


            # ABA 4: Editar Prato
            with gr.TabItem("Editar Prato"):
                in_edit_id = gr.Textbox(label="ID do Prato")
                with gr.Row():
                    in_edit_nome = gr.Textbox(label="Novo Nome")
                    in_edit_preco = gr.Textbox(label="Novo Preço Normal")
                    in_edit_preco_promo = gr.Number(label="Novo Preço Promocional (Deixe 0 p/ remover)") # NOVO
                in_edit_foto = gr.Textbox(label="Nova URL")
                btn_edit = gr.Button("Atualizar Dados", variant="secondary")
                out_msg_edit = gr.Textbox(label="Status")
                btn_edit.click(gr_editar, [in_edit_id, in_edit_nome, in_edit_preco, in_edit_preco_promo, in_edit_foto, sessao_usuario], [out_msg_edit, output_table_admin])

            # ABA 5: Remover Prato
            with gr.TabItem("Remover Prato"):
                in_del_id = gr.Textbox(label="ID do Prato")
                btn_del = gr.Button("Excluir Prato", variant="stop")
                out_msg_del = gr.Textbox(label="Status")
                btn_del.click(gr_excluir, [in_del_id, sessao_usuario], [out_msg_del, output_table_admin])

            # ABA 6: Gerar QR Code
            with gr.TabItem("Gerar QR Code"):
                gr.Markdown("### Criar QR Code para as Mesas")
                with gr.Row():
                    with gr.Column():
                        in_link_base = gr.Textbox(label="Link Público do Cardápio (Gerado pelo Gradio Share)", placeholder="Ex: https://xxxx.gradio.live", value="http://localhost:7860")
                        in_mesa = gr.Number(label="Número da Mesa (Deixe 0 para Balcão)", value=1, precision=0)
                        btn_qr = gr.Button("Criar QR Code", variant="primary")
                    with gr.Column():
                        out_qr = gr.Image(label="QR Code", type="pil")
                
                btn_qr.click(fn=gerar_qr_code, inputs=[in_mesa, in_link_base, sessao_usuario], outputs=[out_qr])

    # ==========================================
    # EVENTOS DE TRANSIÇÃO E LOGOUT
    # ==========================================
    btn_login.click(
        fn=validar_login, 
        inputs=[login_user, login_senha], 
        outputs=[sessao_usuario, sessao_perfil, tela_login, tela_admin, tela_cozinha, msg_login]
    ).then(
        fn=gr_listar, inputs=[sessao_usuario], outputs=[output_table_admin]
    ).then(
        fn=gr_listar, inputs=[sessao_usuario], outputs=[output_table_cozinha]
    ).then(
        fn=listar_pedidos, inputs=[sessao_usuario], outputs=[tabela_pedidos]
    ).then(
        fn=gr_listar_ingredientes, inputs=[sessao_usuario], outputs=[tabela_ingredientes]
    )
    
    # Eventos de logout para os dois painéis
    btn_logout_admin.click(fn=fazer_logout, inputs=[], outputs=[sessao_usuario, sessao_perfil, tela_login, tela_admin, tela_cozinha])
    btn_logout_coz.click(fn=fazer_logout, inputs=[], outputs=[sessao_usuario, sessao_perfil, tela_login, tela_admin, tela_cozinha])

if __name__ == "__main__":
    demo.launch(server_port=7861, share=False)