import sqlite3
import gradio as gr
import os
from datetime import datetime

DIRETORIO = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(DIRETORIO, "pratos.db")

# ENVIAR PEDIDO
def registrar_pedido(descricao_pedido, request: gr.Request):
    query_params = dict(request.query_params)
    id_restaurante = query_params.get('rest', '')
    numero_mesa = query_params.get('mesa', 'Balcão / Viagem')

    if not id_restaurante: return ""
    if not descricao_pedido or descricao_pedido.strip() == "": return ""

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT NOT NULL, data_hora TEXT NOT NULL, status TEXT DEFAULT 'Pendente', id_restaurante TEXT, numero_mesa TEXT)''')
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN numero_mesa TEXT DEFAULT 'Balcão'")
    except: pass 
    
    cursor.execute("INSERT INTO pedidos (descricao, data_hora, status, id_restaurante, numero_mesa) VALUES (?, ?, 'Pendente', ?, ?)", 
                   (descricao_pedido, agora, id_restaurante, numero_mesa))
    conn.commit()
    conn.close()
    
    gr.Info("Pedido enviado! A cozinha já está preparando.")
    return "" 

# LISTAR PRATOS (Com Promoções)

def listar_pratos(request: gr.Request):
    query_params = dict(request.query_params)
    id_restaurante = query_params.get('rest', '')
    numero_mesa = query_params.get('mesa', '')

    if not id_restaurante:
        return "<div class='container' style='justify-content: center; text-align: center; margin-top: 50px;'><h2>Bem-vindo ao CARD🍔N!</h2><p>Por favor, acesse o cardápio usando o link ou QR Code da sua mesa.</p></div>"

    conn = sqlite3.connect(BANCO)
    cursor = conn.cursor()
    
    query = '''
        SELECT DISTINCT p.id, p.nome, p.preco, p.preco_promocional, p.foto 
        FROM pratos p
        WHERE p.id_restaurante = ?
        AND p.id NOT IN (
            SELECT pi.id_prato 
            FROM prato_ingredientes pi
            JOIN ingredientes i ON pi.id_ingrediente = i.id
            WHERE i.status = 'Esgotado'
        )
    '''
    
    try: cursor.execute(query, (id_restaurante,))
    except: 
        return "<div class='container'><h2>Aguardando atualização do cardápio pelo restaurante...</h2></div>"
        
    pratos = cursor.fetchall()
    conn.close()

    if not pratos: return "<div class='container'><h2>Nenhum prato disponível neste restaurante no momento.</h2></div>"

    aviso_mesa = f"<div class='aviso-mesa'>Você está pedindo na <strong>Mesa {numero_mesa}</strong></div>" if numero_mesa else "<div class='aviso-mesa'>Pedido para <strong>Balcão / Retirada</strong></div>"

    html = aviso_mesa + '<div class="container">'
    for id_prato, nome, preco, preco_promo, foto in pratos:
        imagem = foto if foto else "https://cdn-icons-png.flaticon.com/512/813/813789.png"
        nome_seguro = nome.replace("'", "\\'")
        id_input = f"qtd-{id_prato}"
        
        if preco_promo and preco_promo > 0:
            preco_html = f"<div class='preco'><del style='color:#999; font-size:16px; margin-right:8px;'>R$ {preco:.2f}</del><span style='color:#d32f2f;'>R$ {preco_promo:.2f} </span></div>"
        else:
            preco_html = f"<div class='preco'>R$ {preco:.2f}</div>"
        
        html += f"""
        <div class="card">
            <img src="{imagem}" class="imagem">
            <div class="conteudo">
                <div class="titulo">{nome}</div>
                {preco_html}
                
                <div class="qtd-wrapper">
                    <button class="btn-qtd btn-minus" data-target="{id_input}">-</button>
                    <input type="number" class="input-qtd" id="{id_input}" value="1" min="1">
                    <button class="btn-qtd btn-plus" data-target="{id_input}">+</button>
                </div>

                <button class="btn-add" data-nome="{nome_seguro}" data-input="{id_input}">Adicionar</button>
            </div>
        </div>
        """
    html += '</div>'
    return html


# CSS E JAVASCRIPT

cabecalho = """
<style>
    /* CORREÇÃO DO DARK MODE: Força o fundo claro e o texto escuro globalmente */
    body, .gradio-container { background-color: #f5f5f5 !important; }
    h1, h2, h3, p { color: #222 !important; } 

    .aviso-mesa { background: #ffcc00; color: #333 !important; padding: 10px; text-align: center; font-size: 18px; font-weight: bold; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
    
    .container { display:flex; flex-wrap:wrap; gap:20px; padding-bottom:100px; color: #333 !important; }
    
    .card { width:250px; background:white !important; color:#333 !important; border-radius:12px; overflow:hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition:0.2s; }
    .card:hover { transform:scale(1.02); }
    .imagem { width:100%; height:180px; object-fit:cover; }
    .conteudo { padding:15px; display: flex; flex-direction: column; gap: 8px; }
    .titulo { font-size:22px; font-weight:bold; margin:0; line-height: 1.2; color: #111 !important; }
    .preco { color:green !important; font-size:20px; font-weight:bold; margin: 0 0 5px 0;}
    
    .qtd-wrapper { display: flex; align-items: center; justify-content: space-between; background: #eee !important; border-radius: 8px; padding: 5px; margin-bottom: 5px; }
    .btn-qtd { background: white !important; color: #333 !important; border: 1px solid #ccc; border-radius: 5px; width: 32px; height: 32px; font-size: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
    .btn-qtd:hover { background: #ddd !important; }
    .input-qtd { width: 50px; text-align: center; border: none; background: transparent !important; font-size: 16px; font-weight: bold; color: #333 !important; }
    .input-qtd::-webkit-inner-spin-button, .input-qtd::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    .input-qtd { -moz-appearance: textfield; }

    .btn-add { background-color: #e0e0e0 !important; color: #333 !important; border: none; padding: 10px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: 0.2s; width: 100%; }
    .btn-add:hover { background-color: #4CAF50 !important; color: white !important; }
    
    .botao-cozinha { position:fixed; bottom:25px; right:25px; background:#ff5722 !important; color:white !important; border:none; border-radius:50px; padding:18px 28px; font-size:18px; font-weight:bold; cursor:pointer; box-shadow:0 4px 10px rgba(0,0,0,0.3); z-index:999; transition: 0.2s; }
    .botao-cozinha:hover { background:#e64a19 !important; transform:scale(1.05); }
    
    #toast { display: none; position: fixed; bottom: 90px; right: 25px; background: #333 !important; color: #fff !important; padding: 12px 20px; border-radius: 8px; z-index: 1000; box-shadow: 0 4px 6px rgba(0,0,0,0.2); font-weight: bold; }
    
    /* MODAL DO CARRINHO */
    .modal-carrinho { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; align-items: center; justify-content: center; }
    .modal-conteudo { background: white !important; color: #333 !important; padding: 25px; border-radius: 16px; width: 90%; max-width: 450px; max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
    .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-bottom: 15px; }
    .modal-header h3 { margin: 0; font-size: 22px; color: #111 !important; }
    .btn-fechar-modal { background: none; border: none; font-size: 24px; cursor: pointer; color: #666 !important; }
    .carrinho-lista { overflow-y: auto; flex-grow: 1; margin-bottom: 20px; padding-right: 5px; }
    
    .carrinho-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; color: #333 !important; }
    .carrinho-item-info { font-size: 16px; font-weight: 500; flex-grow: 1; color: #333 !important; }
    .qtd-wrapper-cart { display: flex; align-items: center; gap: 12px; background: #f9f9f9 !important; padding: 4px 8px; border-radius: 8px; border: 1px solid #eee;}
    .btn-qtd-cart { background: white !important; color: #333 !important; border: 1px solid #ccc; border-radius: 6px; width: 30px; height: 30px; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold; transition: 0.2s;}
    .btn-cart-minus { color: #d32f2f !important; }
    .btn-cart-minus:hover { background: #ffebee !important; border-color: #ef9a9a; }
    .btn-cart-plus { color: #388e3c !important; }
    .btn-cart-plus:hover { background: #e8f5e9 !important; border-color: #a5d6a7; }
    .qtd-text-cart { font-weight: bold; font-size: 16px; min-width: 20px; text-align: center; color: #333 !important; }
    
    .btn-confirmar-pedido { background: #4CAF50 !important; color: white !important; border: none; width: 100%; padding: 14px; font-size: 18px; font-weight: bold; border-radius: 10px; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .btn-confirmar-pedido:hover { background: #43a047 !important; }
    .carrinho-vazio-msg { text-align: center; color: #888 !important; padding: 20px 0; font-style: italic; }

    .escondido { display: none !important; }
</style>

<script>
    window.carrinho = [];

    window.atualizarBotaoFlutuante = function() {
        let totalItens = window.carrinho.reduce((acc, item) => acc + item.qtd, 0);
        let btn = document.getElementById('btn-enviar-cozinha');
        if(btn) {
            btn.innerText = totalItens > 0 ? `Ver Carrinho (${totalItens} itens)` : "Carrinho Vazio";
            if(totalItens === 0) document.getElementById('modal-carrinho-janela').style.display = "none";
        }
    };

    window.renderizarCarrinhoModal = function() {
        let listaDiv = document.getElementById('carrinho-lista-itens');
        if(!listaDiv) return;
        listaDiv.innerHTML = "";

        if(window.carrinho.length === 0) {
            listaDiv.innerHTML = "<div class='carrinho-vazio-msg'>Seu carrinho está vazio. Adicione itens do cardápio!</div>";
            return;
        }

        window.carrinho.forEach((item, index) => {
            let itemHtml = `
                <div class="carrinho-item">
                    <div class="carrinho-item-info">${item.nome}</div>
                    <div class="qtd-wrapper-cart">
                        <button class="btn-qtd-cart btn-cart-minus" data-index="${index}">-</button>
                        <span class="qtd-text-cart">${item.qtd}</span>
                        <button class="btn-qtd-cart btn-cart-plus" data-index="${index}">+</button>
                    </div>
                </div>
            `;
            listaDiv.innerHTML += itemHtml;
        });
    };

    document.addEventListener('click', function(e) {
        let btnMinus = e.target.closest('.btn-minus');
        if (btnMinus) {
            let input = document.getElementById(btnMinus.getAttribute('data-target'));
            if (input) {
                let valor = parseInt(input.value) || 1;
                if (valor > 1) input.value = valor - 1;
            }
        }
        
        let btnPlus = e.target.closest('.btn-plus');
        if (btnPlus) {
            let input = document.getElementById(btnPlus.getAttribute('data-target'));
            if (input) {
                let valor = parseInt(input.value) || 1;
                if (valor < 10) 
                {
                    input.value = valor + 1;
                }
            }
        }

        let btnAdd = e.target.closest('.btn-add');
        if (btnAdd) {
            let nomePrato = btnAdd.getAttribute('data-nome');
            let input = document.getElementById(btnAdd.getAttribute('data-input'));
            let qtd = input ? (parseInt(input.value) || 1) : 1;
            if (qtd < 1) qtd = 1;

            if (nomePrato) {
                let itemExistente = window.carrinho.find(item => item.nome === nomePrato);

                if (itemExistente) {
                    let novaQtd = itemExistente.qtd + qtd;
                    itemExistente.qtd = Math.min(novaQtd, 10);
                } else {
                    window.carrinho.push({
                        nome: nomePrato,
                        qtd: Math.min(qtd, 10)
                    });
                }

                window.atualizarBotaoFlutuante();

                let toast = document.getElementById('toast');
                if(toast) {
                    toast.innerText = `${qtd}x ${nomePrato} adicionado!`;
                    toast.style.display = "block";
                    setTimeout(() => { toast.style.display = "none"; }, 1800);
                }

                if (input) input.value = 1;
            }
        }
        
        let btnCartMinus = e.target.closest('.btn-cart-minus');
        if (btnCartMinus) {
            let index = parseInt(btnCartMinus.getAttribute('data-index'));
            if (window.carrinho[index].qtd > 1) window.carrinho[index].qtd -= 1;
            else window.carrinho.splice(index, 1);
            window.renderizarCarrinhoModal(); 
            window.atualizarBotaoFlutuante(); 
        }

        let btnCartPlus = e.target.closest('.btn-cart-plus');
        if (btnCartPlus) {
            let index = parseInt(btnCartPlus.getAttribute('data-index'));

            if (window.carrinho[index].qtd < 10) {
                window.carrinho[index].qtd += 1;
            }

            window.renderizarCarrinhoModal();
            window.atualizarBotaoFlutuante();
        }

        let btnVerCarrinho = e.target.closest('#btn-enviar-cozinha');
        if (btnVerCarrinho) {
            if (window.carrinho.length === 0) return;
            window.renderizarCarrinhoModal();
            document.getElementById('modal-carrinho-janela').style.display = "flex";
        }

        if (e.target.closest('#btn-fechar-modal-carrinho') || e.target.id === 'modal-carrinho-janela') {
            document.getElementById('modal-carrinho-janela').style.display = "none";
        }

        let btnConfirmar = e.target.closest('#btn-confirmar-final');
        if (btnConfirmar) {
            if (window.carrinho.length === 0) return;
            
            let pedido_formatado = window.carrinho.map(item => `${item.qtd}x ${item.nome}`).join("  +  ");
            
            document.getElementById('modal-carrinho-janela').style.display = "none";
            localStorage.setItem('ultimo_pedido_cardon', pedido_formatado);

            let btnOculto = document.querySelector('#btn_enviar_pedido_oculto');
            if(btnOculto) btnOculto.click();
            
            window.carrinho = [];
            window.atualizarBotaoFlutuante();
        }
    });
</script>
"""

codigo_js_oficial_gradio = """
(texto_antigo) => {
    let pedido_final = localStorage.getItem('ultimo_pedido_cardon') || "";
    localStorage.removeItem('ultimo_pedido_cardon');
    return pedido_final;
}
"""

with gr.Blocks(title="Cardápio Digital", head=cabecalho) as demo:
    gr.Markdown("# CARD🍔N\n### Monte seu carrinho e faça seu pedido")

    caixa_pedido = gr.Textbox(elem_classes="escondido")
    btn_oculto = gr.Button("Oculto", elem_id="btn_enviar_pedido_oculto", elem_classes="escondido")
    
    btn_oculto.click(fn=registrar_pedido, inputs=[caixa_pedido], outputs=[caixa_pedido], js=codigo_js_oficial_gradio)

    gr.HTML("""
    <div id="toast">Item adicionado!</div>
    <button id="btn-enviar-cozinha" class="botao-cozinha">Carrinho Vazio</button>
    <div class="modal-carrinho" id="modal-carrinho-janela">
        <div class="modal-conteudo">
            <div class="modal-header">
                <h3>Seu Carrinho</h3>
                <button class="btn-fechar-modal" id="btn-fechar-modal-carrinho">&times;</button>
            </div>
            <div class="carrinho-lista" id="carrinho-lista-itens"></div>
            <button class="btn-confirmar-pedido" id="btn-confirmar-final">Confirmar e Enviar para Cozinha</button>
        </div>
    </div>
    """)

    cardapio = gr.HTML()
    demo.load(fn=listar_pratos, outputs=cardapio)

if __name__ == "__main__":
    demo.launch(server_port=7860,share=True)
