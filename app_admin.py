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
    
    try: 
        cursor.execute("ALTER TABLE pedidos ADD COLUMN numero_mesa TEXT DEFAULT 'Balcão'")
    except: 
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
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
            id_restaurante TEXT
        )
    ''')

    # NOVA TABELA: Ingredientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingredientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            status TEXT DEFAULT 'Disponível',
            id_restaurante TEXT
        )
    ''')

    # NOVA TABELA: Vínculo entre Prato e Ingredientes (Muitos para Muitos)
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

def registrar_usuario(usuario, senha):
    if not usuario or not senha:
        return "Erro: Preencha usuário e senha."
    
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    try:
        id_restaurante = str(uuid.uuid4().hex)[:8]
        cursor.execute("INSERT INTO usuarios (username, password, id_restaurante) VALUES (?, ?, ?)", 
                       (usuario, hash_senha(senha), id_restaurante))
        conn.commit()
        msg = f"Conta criada! Seu ID de Restaurante é: {id_restaurante}. Faça login."
    except sqlite3.IntegrityError:
        msg = "Erro: Nome de usuário já existe."
    finally:
        conn.close()
    
    return msg

def validar_login(usuario, senha):
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("SELECT id_restaurante FROM usuarios WHERE username = ? AND password = ?", 
                   (usuario, hash_senha(senha)))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        id_restaurante = resultado[0]
        return id_restaurante, gr.update(visible=False), gr.update(visible=True), f"Bem-vindo! ID do seu Restaurante: {id_restaurante}"
    else:
        return None, gr.update(visible=True), gr.update(visible=False), "❌ Usuário ou senha incorretos."

def fazer_logout():
    return None, gr.update(visible=True), gr.update(visible=False)

# -----------------------------
# 2. FUNÇÕES DE PEDIDOS
# -----------------------------
def listar_pedidos(id_rest):
    if not id_rest: return pd.DataFrame()
    conn = sqlite3.connect(BANCO)
    # Buscando a 'numero_mesa' para mostrar na tabela
    df = pd.read_sql_query("SELECT id, numero_mesa as 'Mesa', descricao, data_hora, status FROM pedidos WHERE id_restaurante = ? ORDER BY id DESC", conn, params=(id_rest,))
    conn.close()
    return df

def atualizar_status_pedido(id_pedido, novo_status, id_rest):
    if not id_pedido or not novo_status:
        return "Erro: Informe o ID do pedido e o novo status.", listar_pedidos(id_rest)
    
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    
    # Se o status for de finalização, deleta o pedido do banco
    if novo_status in ["Entregue/Finalizado", "Cancelado"]:
        cursor.execute("DELETE FROM pedidos WHERE id = ? AND id_restaurante = ?", 
                       (id_pedido, id_rest))
        acao_realizada = f"removido da fila ({novo_status})"
    
    # Caso contrário, apenas atualiza o texto do status
    else:
        cursor.execute("UPDATE pedidos SET status = ? WHERE id = ? AND id_restaurante = ?", 
                       (novo_status, id_pedido, id_rest))
        acao_realizada = f"atualizado para '{novo_status}'"
        
    linhas = cursor.rowcount
    conn.commit()
    conn.close()
    
    if linhas > 0:
        return f"Pedido #{id_pedido} {acao_realizada}!", listar_pedidos(id_rest)
    return "Erro: Pedido não encontrado ou não pertence a este restaurante.", listar_pedidos(id_rest)

# -----------------------------
# 3. LÓGICA DE INGREDIENTES E FILTRO DE CATÁLOGO
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

# -----------------------------
# 4. CRUD DE PRATOS (MODIFICADO COM FILTRO DE INGREDIENTES)
# -----------------------------
def gr_listar(id_rest):
    if not id_rest: return pd.DataFrame()
    conn = sqlite3.connect(BANCO)
    
    # Query inteligente: Seleciona apenas pratos cujos ingredientes vinculados NÃO estejam "Esgotados"
    query = '''
        SELECT DISTINCT p.id, p.nome, p.preco, p.foto 
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
        df['foto'] = df['foto'].apply(
            lambda x: f'<img src="{x}" width="50" height="50" style="border-radius: 5px;">'
            if pd.notna(x) and x != "" else "Sem foto"
        )
    return df

def gr_criar(nome, preco, foto, ids_ingredientes_str, id_rest):
    if not nome or not preco:
        return "Erro: Nome e Preço são obrigatórios", gr_listar(id_rest)

    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pratos (nome, preco, foto, id_restaurante) VALUES (?, ?, ?, ?)', 
                   (nome, float(preco), foto, id_rest))
    id_prato_criado = cursor.lastrowid

    # Vincula os ingredientes digitados (Ex: "1, 2, 3") ao prato
    if ids_ingredientes_str:
        try:
            ids_ingredientes = [int(x.strip()) for x in ids_ingredientes_str.split(",") if x.strip().isdigit()]
            for id_ing in ids_ingredientes:
                cursor.execute('INSERT OR IGNORE INTO prato_ingredientes (id_prato, id_ingrediente) VALUES (?, ?)', (id_prato_criado, id_ing))
        except Exception:
            pass

    conn.commit()
    conn.close()
    return f"Prato '{nome}' criado com sucesso e vinculado aos ingredientes!", gr_listar(id_rest)

def gr_excluir(id_busca, id_rest):
    if not id_busca: return "Erro: Forneça o ID", gr_listar(id_rest)
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pratos WHERE id = ? AND id_restaurante = ?", (id_busca, id_rest))
    cursor.execute("DELETE FROM prato_ingredientes WHERE id_prato = ?", (id_busca,))
    linhas_afetadas = cursor.rowcount
    conn.commit()
    conn.close()

    if linhas_afetadas > 0:
        return f"Prato ID {id_busca} removido!", gr_listar(id_rest)
    return "Erro: ID não encontrado", gr_listar(id_rest)

def gr_editar(id_busca, nome, preco, foto, id_rest):
    if not id_busca: return "Erro: Forneça o ID do prato", gr_listar(id_rest)
    campos, valores = [], []
    if nome: campos.append("nome = ?"); valores.append(nome)
    if preco: campos.append("preco = ?"); valores.append(float(preco))
    if foto: campos.append("foto = ?"); valores.append(foto)
    if not campos: return "Nenhum dado informado", gr_listar(id_rest)

    valores.extend([id_busca, id_rest])
    query = f"UPDATE pratos SET {', '.join(campos)} WHERE id = ? AND id_restaurante = ?"
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    cursor.execute(query, tuple(valores))
    linhas_afetadas = cursor.rowcount
    conn.commit()
    conn.close()

    if linhas_afetadas > 0:
        return f"Prato ID {id_busca} atualizado!", gr_listar(id_rest)
    return "Erro: Prato não encontrado", gr_listar(id_rest)

# -----------------------------
# 5. INTERFACE GRADIO
# -----------------------------
inicializar_banco()


def gerar_qr_code(numero_mesa, id_rest):
        if not id_rest: return None
        url_base = "http://localhost:7860" # Troque pelo seu IP se for usar no celular
        
        if numero_mesa and numero_mesa > 0:
            url_final = f"{url_base}/?rest={id_rest}&mesa={int(numero_mesa)}"
        else:
            url_final = f"{url_base}/?rest={id_rest}"
            
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url_final)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").get_image()

with gr.Blocks(title="Gestão de Restaurante") as demo:
    sessao_usuario = gr.State(None)

    # --- TELA DE LOGIN ---
    with gr.Column(visible=True) as tela_login:
        gr.Markdown("# Acesso ao Sistema CARD🍔N")
        with gr.Tab("Login"):
            login_user = gr.Textbox(label="Usuário")
            login_senha = gr.Textbox(label="Senha", type="password")
            btn_login = gr.Button("Entrar", variant="primary")
            msg_login = gr.Markdown("")
        with gr.Tab("Registrar Novo Restaurante"):
            reg_user = gr.Textbox(label="Novo Usuário")
            reg_senha = gr.Textbox(label="Nova Senha", type="password")
            btn_registrar = gr.Button("Registrar")
            msg_reg = gr.Markdown("")
            btn_registrar.click(registrar_usuario, inputs=[reg_user, reg_senha], outputs=[msg_reg])

    # --- TELA ADMIN ---
    with gr.Column(visible=False) as tela_admin:
        with gr.Row():
            titulo_admin = gr.Markdown("# CARD🍔N - Gestão de Restaurante")
            btn_logout = gr.Button("Sair", size="sm")

        with gr.Tabs():

            # --- NOVA ABA: Gerador de QR Code ---
            with gr.TabItem("Gerar QR Code"):
                gr.Markdown("### 🖨️ Criar QR Code para as Mesas")
                with gr.Row():
                    with gr.Column():
                        in_mesa = gr.Number(label="Número da Mesa (Deixe 0 para Balcão)", value=1, precision=0)
                        btn_qr = gr.Button("Criar QR Code", variant="primary")
                    with gr.Column():
                        out_qr = gr.Image(label="QR Code", type="pil")
                
                btn_qr.click(fn=gerar_qr_code, inputs=[in_mesa, sessao_usuario], outputs=[out_qr])

            # --- ABA 1: Cozinha ---
            with gr.TabItem("Fila de Pedidos (Cozinha)"):
                tabela_pedidos = gr.Dataframe(label="Pedidos Recebidos", interactive=False)
                timer_pedidos = gr.Timer(5)
                timer_pedidos.tick(fn=listar_pedidos, inputs=[sessao_usuario], outputs=tabela_pedidos)

                gr.Markdown("### Atualizar Status do Pedido")
                with gr.Row():
                    in_id_pedido = gr.Number(label="ID do Pedido", precision=0)
                    in_status_pedido = gr.Dropdown(choices=["Pendente", "Preparando", "Pronto para Retirada", "Entregue/Finalizado", "Cancelado"], label="Novo Status")
                    btn_status = gr.Button("Confirmar Mudança", variant="primary")
                out_msg_status = gr.Textbox(label="Status da Operação")
                btn_status.click(fn=atualizar_status_pedido, inputs=[in_id_pedido, in_status_pedido, sessao_usuario], outputs=[out_msg_status, tabela_pedidos])

            # --- ABA 2: Lista de Pratos Ativos ---
            with gr.TabItem("Catálogo de Pratos Ativos"):
                gr.Markdown("(Pratos com ingredientes em falta ocultam-se automaticamente aqui)")
                btn_refresh = gr.Button("Atualizar Catálogo")
                output_table = gr.Dataframe(label="Cardápio Ativo", datatype=["number", "str", "number", "html"], wrap=True)
                btn_refresh.click(fn=gr_listar, inputs=[sessao_usuario], outputs=output_table)
                
            # --- NOVA ABA 3: Gestão de Ingredientes ---
            with gr.TabItem("Gestão de Ingredientes"):
                tabela_ingredientes = gr.Dataframe(label="Seus Ingredientes em Estoque", interactive=False)
                btn_refresh_ing = gr.Button("Atualizar Lista de Estoque")
                btn_refresh_ing.click(fn=gr_listar_ingredientes, inputs=[sessao_usuario], outputs=tabela_ingredientes)
                
                with gr.Row():
                    with gr.Group():
                        gr.Markdown("### Adicionar Novo Ingrediente")
                        in_ing_nome = gr.Textbox(label="Nome do Ingrediente (Ex: Queijo Cheddar)")
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

            # --- ABA 4: Cadastrar Pratos ---
            with gr.TabItem("Cadastrar Novo Prato"):
                with gr.Row():
                    in_nome = gr.Textbox(label="Nome do Prato")
                    in_preco = gr.Number(label="Preço (R$)")
                in_foto = gr.Textbox(label="URL da Foto")
                in_prato_ings = gr.Textbox(label="IDs dos Ingredientes vinculados (Separados por vírgula, ex: 1, 4, 7)")
                
                btn_create = gr.Button("Salvar Prato", variant="primary")
                out_msg_create = gr.Textbox(label="Status")
                btn_create.click(gr_criar, [in_nome, in_preco, in_foto, in_prato_ings, sessao_usuario], [out_msg_create, output_table])

            # --- ABA 5: Editar ---
            with gr.TabItem("Editar Prato"):
                in_edit_id = gr.Textbox(label="ID do Prato")
                with gr.Row():
                    in_edit_nome = gr.Textbox(label="Novo Nome")
                    in_edit_preco = gr.Textbox(label="Novo Preço")
                in_edit_foto = gr.Textbox(label="Nova URL")
                btn_edit = gr.Button("Atualizar Dados", variant="secondary")
                out_msg_edit = gr.Textbox(label="Status")
                btn_edit.click(gr_editar, [in_edit_id, in_edit_nome, in_edit_preco, in_edit_foto, sessao_usuario], [out_msg_edit, output_table])

            # --- ABA 6: Excluir ---
            with gr.TabItem("Remover Prato"):
                in_del_id = gr.Textbox(label="ID do Prato")
                btn_del = gr.Button("Excluir Prato", variant="stop")
                out_msg_del = gr.Textbox(label="Status")
                btn_del.click(gr_excluir, [in_del_id, sessao_usuario], [out_msg_del, output_table])


    

    # Chamadas do Painel de Login
    btn_login.click(
        fn=validar_login, inputs=[login_user, login_senha], outputs=[sessao_usuario, tela_login, tela_admin, titulo_admin]
    ).then(
        fn=gr_listar, inputs=[sessao_usuario], outputs=[output_table]
    ).then(
        fn=listar_pedidos, inputs=[sessao_usuario], outputs=[tabela_pedidos]
    ).then(
        fn=gr_listar_ingredientes, inputs=[sessao_usuario], outputs=[tabela_ingredientes]
    )
    
    btn_logout.click(fn=fazer_logout, inputs=[], outputs=[sessao_usuario, tela_login, tela_admin])




if __name__ == "__main__":
    demo.launch(server_port=7861,share=True)