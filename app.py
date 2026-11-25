import os
import urllib.parse
import mysql.connector
from flask import Flask, render_template, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'patas_em_casa_chave_padrao_2026')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CA_PEM_PATH = os.path.join(BASE_DIR, 'ca.pem')

# Configuração do Banco de Dados MySQL
database_url = os.environ.get('DATABASE_URL')

if database_url:
    parsed_url = urllib.parse.urlparse(database_url)
    DB_CONFIG = {
        'host': parsed_url.hostname,
        'user': parsed_url.username,
        'password': parsed_url.password,
        'port': parsed_url.port or 3306,
        'ssl_ca': CA_PEM_PATH if os.path.exists(CA_PEM_PATH) else None,
        'ssl_disabled': not os.path.exists(CA_PEM_PATH)
    }
    DB_NAME = parsed_url.path.lstrip('/')
else:
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', ''),
        'port': int(os.environ.get('DB_PORT', 3306))
    }
    DB_NAME = os.environ.get('DB_NAME', 'patas_em_casa_db')


def get_db_connection():
    config = DB_CONFIG.copy()
    config['database'] = DB_NAME
    return mysql.connector.connect(**config)


def init_db():
    """Cria o banco de dados, as tabelas e popula os pets iniciais se estiver vazio."""
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

        # Tabela de Usuários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(150) NOT NULL UNIQUE,
                senha_hash VARCHAR(255) NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de Pets
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

        # Tabela de Interesses de Adoção
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interesses_adocao (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pet_id INT NOT NULL,
                usuario_id INT NOT NULL,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unica_solicitacao (pet_id, usuario_id),
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)

        # Popula com os 12 pets originais se a tabela estiver vazia
        cursor.execute("SELECT COUNT(*) FROM pets")
        if cursor.fetchone()[0] == 0:
            pets_iniciais = [
                ("Mel", "/static/img/mel.jpg", "Filhote de orelhas grandes apoiado em uma mureta", "cao,filhote", "Cão,3 meses,Porte médio", "Curiosa e carinhosa, adora brincar.", "Mel foi resgatada ainda bebê e cresceu cercada de voluntários. É sociável, aprende rápido e se dá bem com crianças. Ideal para uma família ativa que possa ensinar boas maneiras com paciência."),
                ("Bento e Luna", "/static/img/bento-e-luna.jpg", "Gato preto e branco ao lado de um cão marrom e branco", "cao,gato", "Cão,Gato,Dupla inseparável", "Amigos de longa data, preferem ficar juntos.", "Bento é brincalhão e Luna é curiosa e independente. Cresceram juntos e se acalmam um com o outro. Buscamos uma família disposta a adotar os dois e oferecer espaço para ambos."),
                ("Turminha do Abrigo", "/static/img/turminha-do-abrigo.jpg", "Filhotes de cães e um gatinho deitados com um golden retriever", "cao,gato,filhote", "Cães,Gatinho,Filhotes", "Filhotes sociáveis prontos para crescer em família.", "Um grupo animado de filhotes que aprendeu a conviver com cães adultos e gatos. Todos estão em dia com vacinas e vermífugo, e cada um pode ser adotado individualmente."),
                ("Dio", "/static/img/dio.jpg", "Cão preto, grande e peludo, com coleira e peitoral azul e verde", "cao", "Cão,Porte gigante,Adulto", "Um gigante tranquilo de coração enorme.", "Dio é peludo, calmo e adora companhia. Apesar do tamanho, é muito dócil e paciente com crianças. Precisa de espaço, passeios diários e escovação frequente."),
                ("Grafite", "/static/img/grafite.jpg", "Cão cinza de porte grande sentado, usando coleira vermelha", "cao", "Cão,Porte gigante,Adulto", "Elegante, leal e protetor.", "Grafite é observador e muito apegado à família. Precisa de um tutor com experiência em raças grandes, que ofereça rotina, treino e muito carinho."),
                ("Maya", "/static/img/maya.jpg", "Border collie preto e branco sorrindo, com um laço dourado", "cao", "Cão,Porte médio,Muito ativa", "Inteligente, brincalhona e cheia de energia.", "Maya aprende comandos em poucas repetições e adora desafios. Ideal para quem tem quintal ou gosta de caminhadas e atividades ao ar livre."),
                ("Biscoito", "/static/img/biscoito.jpg", "Buldogue francês caramelo em pé sob o sol", "cao", "Cão,Porte pequeno,Adulto", "Companheiro de sofá com muita personalidade.", "Biscoito é afetuoso, curte um cochilo ao sol e se adapta bem a apartamentos. Por ser de focinho curto, deve evitar exercícios intensos em dias quentes."),
                ("Rex", "/static/img/rex.jpg", "Filhote de pastor alemão deitado com a língua para fora", "cao,filhote", "Cão,Filhote,Porte grande", "Filhote esperto, de orelhas atentas.", "Rex está começando a aprender sobre o mundo. É curioso, ativo e vai precisar de socialização, treino e muita paciência para crescer equilibrado."),
                ("Zeca", "/static/img/zeca.jpg", "Cão boxer caramelo olhando para cima de boca aberta, no jardim", "cao", "Cão,Porte grande,Adulto", "Sempre sorrindo e pronto para brincar.", "Zeca é a alegria em forma de cachorro. Sociável e brincalhão, adora correr no jardim e se dá bem com crianças. Precisa gastar bastante energia todos os dias."),
                ("Fred", "/static/img/fred.jpg", "Gato persa laranja e peludo deitado em um sofá cinza", "gato", "Gato,Persa,Pelo longo", "Charmoso, calmo e cheio de pelo.", "Fred é um gato sossegado que gosta de colo e de um ambiente tranquilo. O pelo longo pede escovação diária para evitar nós."),
                ("Cleo", "/static/img/cleo.jpg", "Gata siamesa de olhos azuis sentada em uma mesa de madeira", "gato", "Gata,Siamês,Olhos azuis", "Comunicativa, elegante e muito apegada.", "Cleo conversa com miados, acompanha a família pela casa e adora observar a janela. Prefere um lar com atenção constante e brincadeiras."),
                ("Anúbis", "/static/img/anubis.jpg", "Gato sphynx sem pelos deitado em uma caminha felpuda", "gato", "Gato,Sphynx,Sem pelos", "Curioso, carinhoso e friorento.", "Anúbis procura calor e colo. Por ter a pele exposta, precisa de cobertor, protetor contra o sol e banhos regulares com produtos indicados pelo veterinário.")
            ]
            cursor.executemany("""
                INSERT INTO pets (nome, foto, foto_alt, grupos, etiquetas, resumo, descricao)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, pets_iniciais)
            conn.commit()

        cursor.close()
        conn.close()
        print("MySQL conectado e tabelas prontas!")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")


# ==========================================================
# ROTAS DE PÁGINA E API
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

    pets_formatados = []
    for p in registros:
        pets_formatados.append({
            "id": p['id'],
            "nome": p['nome'],
            "foto": p['foto'],
            "fotoAlt": p['foto_alt'],
            "grupos": p['grupos'].split(','),
            "etiquetas": p['etiquetas'].split(','),
            "resumo": p['resumo'],
            "descricao": p['descricao']
        })
    return jsonify(pets_formatados)


@app.route('/api/sessao', methods=['GET'])
def verificar_sessao():
    if 'usuario_id' in session:
        return jsonify({"logado": True, "email": session['usuario_email']})
    return jsonify({"logado": False, "email": None})


@app.route('/api/login', methods=['POST'])
def login():
    """Autentica um usuário existente ou cria uma nova conta automaticamente."""
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
    else:
        senha_hash = generate_password_hash(senha)
        cursor.execute(
            "INSERT INTO usuarios (email, senha_hash) VALUES (%s, %s)",
            (email, senha_hash)
        )
        conn.commit()
        usuario_id = cursor.lastrowid

    cursor.close()
    conn.close()

    session['usuario_id'] = usuario_id
    session['usuario_email'] = email
    return jsonify({"sucesso": True, "email": email})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"sucesso": True})


@app.route('/api/adotar', methods=['POST'])
def registrar_interesse():
    if 'usuario_id' not in session:
        return jsonify({"erro": "Faça login para registrar interesse."}), 401

    dados = request.get_json() or {}
    pet_id = dados.get('pet_id')
    usuario_id = session['usuario_id']

    if not pet_id:
        return jsonify({"erro": "Pet inválido."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT IGNORE INTO interesses_adocao (pet_id, usuario_id) VALUES (%s, %s)",
            (pet_id, usuario_id)
        )
        conn.commit()
        return jsonify({"sucesso": True, "mensagem": "Interesse registrado no banco de dados!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# Inicializa o banco ao carregar a aplicação (compatível com Gunicorn/Produção)
init_db()

if __name__ == '__main__':
    app.run(debug=True)