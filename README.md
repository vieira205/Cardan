# CARDAN - Gestão de Restaurante

O **CARDAN** é um sistema web interativo para a gestão de pratos de um restaurante. Ele fornece uma interface amigável e moderna para realizar todas as operações essenciais de gerenciamento de dados (CRUD — Criar, Ler, Atualizar e Deletar), garantindo a persistência dos dados de forma eficiente.

## Tecnologias Utilizadas

* **[Python 3.8+](https://www.python.org/):** Linguagem base do projeto.
* **[Gradio](https://www.gradio.app/):** Framework utilizado para construir as interfaces gráficas web responsivas (Frontend e Backend integrados).
* **[SQLite3](https://www.sqlite.org/):** Banco de dados relacional nativo, leve, ACID-compliant, que armazena usuários, pratos, ingredientes, vínculos e pedidos sem necessidade de instalar servidores externos de banco de dados.
* **[Pandas](https://pandas.pydata.org/):** Biblioteca de análise de dados utilizada para espelhar consultas SQL complexas diretamente em DataFrames e renderizar as tabelas dinâmicas do Gradio.
* **[QRCode (com suporte PIL/Pillow)](https://pypi.org/project/qrcode/):** Biblioteca para geração das imagens matriciais dos QR Codes de mesa em formato raster de alta definição.
  
## Requisitos para Execução
1.  **Python Instalado:** Versão 3.8 ou superior.
2.  **Gerenciador de Pacotes PIP:** Atualizado.
3.  **Terminal de Comandos:** PowerShell, Prompt de Comando (CMD) ou Bash.
4.  **Navegador Web:** Qualquer navegador moderno (Chrome, Edge, Firefox, Safari).
   
## Passo a Passo para Instalação

Siga as etapas abaixo para configurar o ambiente do projeto localmente:

1.  **Preparar o arquivo do projeto:**
    Salve a pasta do projeto no seu computador.

2.  **Criar um Ambiente Virtual (Opcional, mas recomendado):**
    No terminal, navegue até a pasta do projeto e execute o comando correspondente ao seu sistema operacional:
    ```bash
    # No Windows:
    python -m venv venv
    .\venv\Scripts\activate

    # No Linux/macOS:
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instalar as dependências:**
    Com o ambiente virtual ativo (ou globalmente), instale as bibliotecas necessárias executando o seguinte comando no terminal:
    ```bash
    pip install -r .\requirements.txt
    ```

## Passo a Passo para Execução

Como o sistema é dividido em dois módulos, você precisará rodar os aplicativos em janelas separadas do terminal.
Passo 1: Executar o Painel do Cliente (Cardápio)

    Abra um terminal, certifique-se de que o venv está ativado e execute o arquivo do cliente:
    Bash

    python app_cliente.py

    O terminal exibirá mensagens de carregamento e fornecerá dois links:

        Local URL: http://localhost:7860 (Para testar no seu próprio computador).

        Public URL (Gradio Share): Um link terminado em .gradio.live (Ex: https://a1b2c3d4.gradio.live). Copie este link público.

Passo 2: Executar o Painel Administrativo/Cozinha

    Abra uma nova janela do terminal, acesse a mesma pasta do projeto, ative o ambiente virtual (venv) e execute o painel administrativo:
    Bash

    python app_admin.py

    Acesse o painel pelo link exibido no terminal (geralmente rodando na porta http://localhost:7861).

Passo 3: Fluxo de Configuração Inicial (Primeiro Acesso)

    Registrar o Restaurante: Na tela de login do Painel Admin (http://localhost:7861), vá na aba "Registrar Novo Restaurante". Crie um usuário e configure duas senhas diferentes: uma para o Administrador e outra para a Cozinha. Clique em Registrar e anote o ID de 8 dígitos do Restaurante gerado na tela.

    Acesso do Administrador: Faça o login usando a senha administrativa. (caso queira testar com um restaurante teste, use o usuario res1 e senha 1234)

        Vá na aba "Gestão de Ingredientes" e cadastre insumos (Ex: ID 1: Pão, ID 2: Carne, ID 3: Queijo).

        Vá na aba "Cadastrar Novo Prato" para registrar seus produtos (Ex: Hambúrguer, R$ 25.00). No campo de ingredientes, informe os IDs criados separados por vírgula (1, 2, 3) para vinculá-los.

    Gerar os QR Codes de Mesa:

        Vá na aba "Gerar QR Code".

        No campo "Link Público do Cardápio", cole o link .gradio.live que você copiou no Passo 1.

        Digite o número da mesa desejada (Ex: 5) e clique em "Criar QR Code".

        Pronto! Qualquer smartphone que escanear essa imagem será direcionado para o cardápio interativo já identificado na Mesa 5, utilizando dados móveis (4G/5G) sem precisar de Wi-Fi local.

Passo 4: Operação do Dia a Dia (Cozinha e Caixa)

    No Painel Admin, clique em Sair (o que limpará a memória do navegador com um reload automático).

    Faça o login utilizando o mesmo usuário, mas digite a Senha da Cozinha (para o mesmo usuário res1, digite a senha 12345 para entrar na aba da cozinha caso queira ja testar o exemplo pronto).

    O sistema revelará o painel limpo, contendo apenas a Fila de Pedidos, o Gerenciador de Caixa e a Visualização de Cardápio Ativo.

    Quando o cliente fizer um pedido pelo celular, ele aparecerá na tela da cozinha instantaneamente. Basta clicar na linha do pedido, selecionar o novo status (Preparando ou Pronto para Retirada) e confirmar.

    No final do consumo, digite o número da mesa na aba "Caixa / Fechar Conta", clique em calcular para obter o extrato detalhado com valores somados automaticamente (incluindo pratos promocionais) e clique em fechar conta para liberar a mesa para o próximo cliente.
