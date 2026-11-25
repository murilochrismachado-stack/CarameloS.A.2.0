import os
import uuid
import urllib.parse
import mysql.connector
from flask import Flask, render_template, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'patas_em_casa_chave_padrao_2026')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CA_PEM_PATH = os.path.join(BASE_DIR, 'ca.pem')

# Pasta para uploads de fotos de produtos pelo administrador
UPLOAD_PRODUTOS_FOLDER = os.path.join(BASE_DIR, 'static', 'img', 'produtos')
os.makedirs(UPLOAD_PRODUTOS_FOLDER, exist_ok=True)

database_url = os.environ.get('DATABASE_URL')

if database_url:
    parsed_url = urllib.parse.urlparse(database_url)
    DB_CONFIG = {
        'host': parsed_url.hostname,
        'user': parsed_url.username,
        'password': parsed_url.password,
        'port': parsed_url.port or 3306,
        'ssl_ca': CA_PEM_PATH if os.path.exists(CA_PEM_PATH) else None,
        'ssl_disabled': not os.path.exists(CA_PEM_PATH),
        'connection_timeout': 15
    }
    DB_NAME = parsed_url.path.lstrip('/')
else:
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', ''),
        'port': int(os.environ.get('DB_PORT', 3306)),
        'connection_timeout': 15
    }
    DB_NAME = os.environ.get('DB_NAME', 'patas_em_casa_db')


def get_db_connection():
    config = DB_CONFIG.copy()
    config['database'] = DB_NAME
    return mysql.connector.connect(**config)


def init_db():
    try:
        temp_config = DB_CONFIG.copy()
        temp_config.pop('database', None)

        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.close()
        conn.close()

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Tabela de Usuários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(150) NOT NULL UNIQUE,
                senha_hash VARCHAR(255) NOT NULL,
                tipo ENUM('cliente', 'admin') DEFAULT 'cliente',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migração automática caso a tabela 'usuarios' já exista sem a coluna 'tipo'
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'tipo'
        """, (DB_NAME,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN tipo ENUM('cliente', 'admin') DEFAULT 'cliente'")
            print("Coluna 'tipo' adicionada à tabela usuarios com sucesso!")

        # 2. Tabela de Pets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                foto VARCHAR(500) NOT NULL,
                foto_alt VARCHAR(255),
                grupos VARCHAR(100) NOT NULL,
                etiquetas VARCHAR(255) NOT NULL,
                resumo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                adotado BOOLEAN DEFAULT FALSE
            )
        """)

        # 3. Tabela de Adoções
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS adocoes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pet_id INT NOT NULL,
                usuario_id INT NOT NULL,
                endereco TEXT NOT NULL,
                vacinas TEXT NOT NULL,
                status_pet VARCHAR(255) DEFAULT 'Saudável e em adaptação no novo lar',
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)

        # 4. Tabela de Produtos da Loja
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                foto VARCHAR(500) NOT NULL,
                grupos VARCHAR(100) NOT NULL,
                etiquetas VARCHAR(255) NOT NULL,
                resumo TEXT NOT NULL,
                preco DECIMAL(10, 2) NOT NULL
            )
        """)

        # 5. Tabela de Compras da Loja
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compras (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT NOT NULL,
                itens_resumo TEXT NOT NULL,
                valor_total DECIMAL(10, 2) NOT NULL,
                data_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)

        # Garante a criação ou atualização da conta administrativa padrão
        cursor.execute("SELECT id FROM usuarios WHERE email = 'admin@patasemcasa.com'")
        admin_existente = cursor.fetchone()
        senha_admin_hash = generate_password_hash('admin123')

        if not admin_existente:
            cursor.execute(
                "INSERT INTO usuarios (email, senha_hash, tipo) VALUES (%s, %s, 'admin')",
                ('admin@patasemcasa.com', senha_admin_hash)
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET tipo = 'admin', senha_hash = %s WHERE email = 'admin@patasemcasa.com'",
                (senha_admin_hash,)
            )

        # Popula Pets iniciais se estiver vazia
        cursor.execute("SELECT COUNT(*) FROM pets")
        if cursor.fetchone()[0] == 0:
            pets_iniciais = [
                ("Mel", "/static/img/mel.jpg", "Filhote de orelhas grandes apoiado em uma mureta", "cao,filhote", "Cão,3 meses,Porte médio", "Curiosa e carinhosa, adora brincar.", "Mel foi resgatada ainda bebê e cresceu cercada de voluntários. É sociável, aprende rápido e se dá bem com crianças."),
                ("Bento e Luna", "/static/img/bento-e-luna.jpg", "Gato preto e branco ao lado de um cão marrom e branco", "cao,gato", "Cão,Gato,Dupla inseparável", "Amigos de longa data, preferem ficar juntos.", "Bento é brincalhão e Luna é curiosa e independente. Cresceram juntos e se acalmam um com o outro."),
                ("Turminha do Abrigo", "/static/img/turminha-do-abrigo.jpg", "Filhotes de cães e um gatinho deitados", "cao,gato,filhote", "Cães,Gatinho,Filhotes", "Filhotes sociáveis prontos para crescer em família.", "Um grupo animado de filhotes que aprendeu a conviver com cães adultos e gatos."),
                ("Dio", "/static/img/dio.jpg", "Cão preto, grande e peludo", "cao", "Cão,Porte gigante,Adulto", "Um gigante tranquilo de coração enorme.", "Dio é peludo, calmo e adora companhia. Apesar do tamanho, é muito dócil e paciente com crianças."),
                ("Grafite", "/static/img/grafite.jpg", "Cão cinza de porte grande sentado", "cao", "Cão,Porte gigante,Adulto", "Elegante, leal e protetor.", "Grafite é observador e muito apegado à família."),
                ("Maya", "/static/img/maya.jpg", "Border collie preto e branco sorrindo", "cao", "Cão,Porte médio,Muito ativa", "Inteligente, brincalhona e cheia de energia.", "Maya aprende comandos em poucas repetições e adora desafios."),
                ("Biscoito", "/static/img/biscoito.jpg", "Buldogue francês caramelo em pé sob o sol", "cao", "Cão,Porte pequeno,Adulto", "Companheiro de sofá com muita personalidade.", "Biscoito é afetuoso, curte um cochilo ao sol e se adapta bem a apartamentos."),
                ("Rex", "/static/img/rex.jpg", "Filhote de pastor alemão deitado", "cao,filhote", "Cão,Filhote,Porte grande", "Filhote esperto, de orelhas atentas.", "Rex está começando a aprender sobre o mundo. É curioso e ativo."),
                ("Zeca", "/static/img/zeca.jpg", "Cão boxer caramelo olhando para cima", "cao", "Cão,Porte grande,Adulto", "Sempre sorrindo e pronto para brincar.", "Zeca é a alegria em forma de cachorro. Sociável e brincalhão."),
                ("Fred", "/static/img/fred.jpg", "Gato persa laranja e peludo", "gato", "Gato,Persa,Pelo longo", "Charmoso, calmo e cheio de pelo.", "Fred é um gato sossegado que gosta de colo e de um ambiente tranquilo."),
                ("Cleo", "/static/img/cleo.jpg", "Gata siamesa de olhos azuis", "gato", "Gata,Siamês,Olhos azuis", "Comunicativa, elegante e muito apegada.", "Cleo conversa com miados e acompanha a família pela casa."),
                ("Anúbis", "/static/img/anubis.jpg", "Gato sphynx sem pelos", "gato", "Gato,Sphynx,Sem pelos", "Curioso, carinhoso e friorento.", "Anúbis procura calor e colo. Precisa de cobertor e cuidados especiais com a pele.")
            ]
            cursor.executemany("""
                INSERT INTO pets (nome, foto, foto_alt, grupos, etiquetas, resumo, descricao)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, pets_iniciais)

        # Popula Produtos iniciais se estiver vazia
        cursor.execute("SELECT COUNT(*) FROM produtos")
        if cursor.fetchone()[0] == 0:
            img_racao_cao = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23E4F0EA'/%3E%3Ctext x='50%25' y='48%25' font-size='70' text-anchor='middle'%3E🦴%3C/text%3E%3Ctext x='50%25' y='72%25' font-family='sans-serif' font-size='20' font-weight='bold' fill='%232D4A3E' text-anchor='middle'%3ERação Cães%3C/text%3E%3C/svg%3E"
            img_racao_gato = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23E4F0EA'/%3E%3Ctext x='50%25' y='48%25' font-size='70' text-anchor='middle'%3E🐟%3C/text%3E%3Ctext x='50%25' y='72%25' font-family='sans-serif' font-size='20' font-weight='bold' fill='%232D4A3E' text-anchor='middle'%3ERação Gatos%3C/text%3E%3C/svg%3E"
            img_brinq_cao = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23FCE8E0'/%3E%3Ctext x='50%25' y='48%25' font-size='70' text-anchor='middle'%3E🎾%3C/text%3E%3Ctext x='50%25' y='72%25' font-family='sans-serif' font-size='20' font-weight='bold' fill='%23D65A35' text-anchor='middle'%3EBrinquedo Cão%3C/text%3E%3C/svg%3E"
            img_brinq_gato = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23FCE8E0'/%3E%3Ctext x='50%25' y='48%25' font-size='70' text-anchor='middle'%3E🧶%3C/text%3E%3Ctext x='50%25' y='72%25' font-family='sans-serif' font-size='20' font-weight='bold' fill='%23D65A35' text-anchor='middle'%3EBrinquedo Gato%3C/text%3E%3C/svg%3E"

            produtos_iniciais = [
                ("Ração Premium Cães Adultos 10kg", img_racao_cao, "racao,cao", "Ração,Cães,10kg", "Nutrição completa sabor frango e arroz.", 139.90),
                ("Ração Super Premium Gatos Castrados 3kg", img_racao_gato, "racao,gato", "Ração,Gatos,3kg", "Controle de peso e saúde do trato urinário.", 89.50),
                ("Ração Filhotes Cães & Gatos 2kg", img_racao_cao, "racao,cao,gato", "Ração,Filhotes,2kg", "Rica em cálcio e vitaminas para crescimento saudável.", 54.00),
                ("Corda Resistente com Nó", img_brinq_cao, "brinquedo,cao", "Brinquedo,Cães,Mordedor", "Ajuda na limpeza dos dentes e alivia o estresse.", 24.90),
                ("Varinha com Penas e Guizo", img_brinq_gato, "brinquedo,gato", "Brinquedo,Gatos,Interativo", "Estimula o instinto caçador e exercita seu gato.", 19.90),
                ("Bolinha Pula-Pula Atóxica", img_brinq_cao, "brinquedo,cao", "Brinquedo,Cães,Borracha", "Super resistente para brincadeiras no parque.", 29.00)
            ]
            cursor.executemany("""
                INSERT INTO produtos (nome, foto, grupos, etiquetas, resumo, preco)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, produtos_iniciais)

        conn.commit()
        cursor.close()
        conn.close()
        print("MySQL conectado e atualizado com sucesso!")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")


# ==========================================================
# ROTAS PRINCIPAIS
# ==========================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/pets', methods=['GET'])
def listar_pets():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pets WHERE adotado = FALSE ORDER BY id ASC")
    registros = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": p['id'],
        "nome": p['nome'],
        "foto": p['foto'],
        "fotoAlt": p['foto_alt'],
        "grupos": p['grupos'].split(','),
        "etiquetas": p['etiquetas'].split(','),
        "resumo": p['resumo'],
        "descricao": p['descricao']
    } for p in registros])


@app.route('/api/produtos', methods=['GET'])
def listar_produtos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    registros = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": prod['id'],
        "nome": prod['nome'],
        "foto": prod['foto'],
        "grupos": prod['grupos'].split(','),
        "etiquetas": prod['etiquetas'].split(','),
        "resumo": prod['resumo'],
        "preco": float(prod['preco'])
    } for prod in registros])


# ==========================================================
# AUTENTICAÇÃO (CLIENTE E ADMINISTRATIVO)
# ==========================================================

@app.route('/api/sessao', methods=['GET'])
def verificar_sessao():
    if 'usuario_id' in session:
        return jsonify({
            "logado": True,
            "email": session['usuario_email'],
            "tipo": session.get('usuario_tipo', 'cliente')
        })
    return jsonify({"logado": False, "email": None, "tipo": None})


@app.route('/api/login', methods=['POST'])
def login():
    dados = request.get_json() or {}
    email = dados.get('email', '').strip().lower()
    senha = dados.get('senha', '')

    if '@' not in email or '.' not in email:
        return jsonify({"erro": "Digite um e-mail válido."}), 400
    if len(senha) < 6:
        return jsonify({"erro": "A senha precisa ter ao menos 6 caracteres."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    usuario = cursor.fetchone()

    if usuario:
        if not check_password_hash(usuario['senha_hash'], senha):
            cursor.close()
            conn.close()
            return jsonify({"erro": "Senha incorreta para este e-mail."}), 401
        usuario_id = usuario['id']
        tipo = usuario.get('tipo') or 'cliente'
    else:
        senha_hash = generate_password_hash(senha)
        tipo = 'cliente'
        cursor.execute(
            "INSERT INTO usuarios (email, senha_hash, tipo) VALUES (%s, %s, %s)",
            (email, senha_hash, tipo)
        )
        conn.commit()
        usuario_id = cursor.lastrowid

    cursor.close()
    conn.close()

    session['usuario_id'] = usuario_id
    session['usuario_email'] = email
    session['usuario_tipo'] = tipo
    return jsonify({"sucesso": True, "email": email, "tipo": tipo})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"sucesso": True})


# ==========================================================
# ADOÇÃO E LOJA
# ==========================================================

@app.route('/api/adotar', methods=['POST'])
def registrar_adocao():
    if 'usuario_id' not in session:
        return jsonify({"erro": "Faça login para concluir a adoção."}), 401

    dados = request.get_json() or {}
    pet_id = dados.get('pet_id')
    endereco = dados.get('endereco', '').strip()
    vacinas = dados.get('vacinas', '').strip()

    if not pet_id or not endereco or not vacinas:
        return jsonify({"erro": "Preencha o endereço e as informações sobre vacinas."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO adocoes (pet_id, usuario_id, endereco, vacinas) VALUES (%s, %s, %s, %s)",
            (pet_id, session['usuario_id'], endereco, vacinas)
        )
        cursor.execute("UPDATE pets SET adotado = TRUE WHERE id = %s", (pet_id,))
        conn.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/comprar', methods=['POST'])
def registrar_compra():
    if 'usuario_id' not in session:
        return jsonify({"erro": "Faça login para finalizar sua compra."}), 401

    dados = request.get_json() or {}
    itens = dados.get('itens', [])
    valor_total = dados.get('valor_total', 0)

    if not itens:
        return jsonify({"erro": "Seu carrinho está vazio."}), 400

    resumo_str = ", ".join([f"{i['qtd']}x {i['nome']}" for i in itens])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO compras (usuario_id, itens_resumo, valor_total) VALUES (%s, %s, %s)",
            (session['usuario_id'], resumo_str, valor_total)
        )
        conn.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ==========================================================
# PAINÉIS: CLIENTE E ADMINISTRATIVO (COM CADASTRO DE PRODUTOS)
# ==========================================================

@app.route('/api/cliente/painel', methods=['GET'])
def painel_cliente():
    if 'usuario_id' not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    uid = session['usuario_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.id, p.nome AS pet_nome, p.foto AS pet_foto, a.endereco, a.vacinas, a.status_pet,
               DATE_FORMAT(a.data_registro, '%d/%m/%Y') AS data
        FROM adocoes a
        JOIN pets p ON a.pet_id = p.id
        WHERE a.usuario_id = %s
        ORDER BY a.id DESC
    """, (uid,))
    minhas_adocoes = cursor.fetchall()

    cursor.execute("""
        SELECT id, itens_resumo, valor_total, DATE_FORMAT(data_compra, '%d/%m/%Y %H:%i') AS data
        FROM compras
        WHERE usuario_id = %s
        ORDER BY id DESC
    """, (uid,))
    minhas_compras = cursor.fetchall()
    for c in minhas_compras:
        c['valor_total'] = float(c['valor_total'])

    cursor.close()
    conn.close()
    return jsonify({"adocoes": minhas_adocoes, "compras": minhas_compras})


@app.route('/api/admin/painel', methods=['GET'])
def painel_admin():
    if session.get('usuario_tipo') != 'admin':
        return jsonify({"erro": "Acesso restrito a administradores."}), 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.id, u.email AS cliente_email, p.nome AS pet_nome, a.endereco, a.vacinas, a.status_pet,
               DATE_FORMAT(a.data_registro, '%d/%m/%Y') AS data
        FROM adocoes a
        JOIN usuarios u ON a.usuario_id = u.id
        JOIN pets p ON a.pet_id = p.id
        ORDER BY a.id DESC
    """)
    todas_adocoes = cursor.fetchall()

    cursor.execute("""
        SELECT c.id, u.email AS cliente_email, c.itens_resumo, c.valor_total,
               DATE_FORMAT(c.data_compra, '%d/%m/%Y %H:%i') AS data
        FROM compras c
        JOIN usuarios u ON c.usuario_id = u.id
        ORDER BY c.id DESC
    """)
    todas_compras = cursor.fetchall()
    for c in todas_compras:
        c['valor_total'] = float(c['valor_total'])

    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    todos_produtos = cursor.fetchall()
    for prod in todos_produtos:
        prod['preco'] = float(prod['preco'])

    cursor.execute("SELECT COUNT(*) AS total FROM pets WHERE adotado = FALSE")
    disponiveis = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM adocoes")
    adotados = cursor.fetchone()['total']

    cursor.execute("SELECT p.grupos FROM adocoes a JOIN pets p ON a.pet_id = p.id")
    grupos_adotados = cursor.fetchall()
    caes_adotados = sum(1 for g in grupos_adotados if 'cao' in g['grupos'])
    gatos_adotados = sum(1 for g in grupos_adotados if 'gato' in g['grupos'])

    cursor.close()
    conn.close()

    return jsonify({
        "adocoes": todas_adocoes,
        "compras": todas_compras,
        "produtos": todos_produtos,
        "grafico": {
            "total_adocoes": adotados,
            "pets_disponiveis": disponiveis,
            "caes_adotados": caes_adotados,
            "gatos_adotados": gatos_adotados
        }
    })


@app.route('/api/admin/produtos', methods=['POST'])
def adicionar_produto():
    if session.get('usuario_tipo') != 'admin':
        return jsonify({"erro": "Acesso negado."}), 403

    nome = request.form.get('nome', '').strip()
    categoria = request.form.get('categoria', 'racao').strip()
    animal = request.form.get('animal', 'cao').strip()
    etiqueta_extra = request.form.get('etiqueta_extra', '').strip()
    resumo = request.form.get('resumo', '').strip()
    preco_str = request.form.get('preco', '').replace(',', '.').strip()

    if not nome or not resumo or not preco_str:
        return jsonify({"erro": "Preencha nome, descrição e preço do produto."}), 400

    try:
        preco = float(preco_str)
    except ValueError:
        return jsonify({"erro": "Preço inválido."}), 400

    foto_file = request.files.get('foto')
    if foto_file and foto_file.filename != '':
        nome_seguro = secure_filename(foto_file.filename)
        nome_unico = f"{uuid.uuid4().hex}_{nome_seguro}"
        caminho_salvo = os.path.join(UPLOAD_PRODUTOS_FOLDER, nome_unico)
        foto_file.save(caminho_salvo)
        foto_url = f"/static/img/produtos/{nome_unico}"
    else:
        emoji = "🦴" if categoria == "racao" else "🎾"
        label = "Ração" if categoria == "racao" else "Brinquedo"
        foto_url = f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23E4F0EA'/%3E%3Ctext x='50%25' y='48%25' font-size='70' text-anchor='middle'%3E{emoji}%3C/text%3E%3Ctext x='50%25' y='72%25' font-family='sans-serif' font-size='20' font-weight='bold' fill='%232D4A3E' text-anchor='middle'%3E{label}%3C/text%3E%3C/svg%3E"

    grupos = f"{categoria},{animal}"
    etiquetas_lista = [
        "Ração" if categoria == "racao" else "Brinquedo",
        "Cães" if animal == "cao" else ("Gatos" if animal == "gato" else "Cães e Gatos")
    ]
    if etiqueta_extra:
        etiquetas_lista.append(etiqueta_extra)
    etiquetas_str = ",".join(etiquetas_lista)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO produtos (nome, foto, grupos, etiquetas, resumo, preco)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nome, foto_url, grupos, etiquetas_str, resumo, preco))
        conn.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/admin/produtos/<int:produto_id>', methods=['DELETE'])
def remover_produto(produto_id):
    if session.get('usuario_tipo') != 'admin':
        return jsonify({"erro": "Acesso negado."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"sucesso": True})


@app.route('/api/admin/status-pet', methods=['POST'])
def atualizar_status_pet():
    if session.get('usuario_tipo') != 'admin':
        return jsonify({"erro": "Acesso negado."}), 403

    dados = request.get_json() or {}
    adocao_id = dados.get('adocao_id')
    novo_status = dados.get('status_pet', '').strip()

    if not adocao_id or not novo_status:
        return jsonify({"erro": "Dados inválidos."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE adocoes SET status_pet = %s WHERE id = %s", (novo_status, adocao_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"sucesso": True})


init_db()

if __name__ == '__main__':
    app.run(debug=True)