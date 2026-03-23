import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session

from votacao import votacao_bp

app = Flask(__name__)
app.secret_key = 'chave_secreta_next_move' 
app.register_blueprint(votacao_bp)
from portaria import portaria_bp
app.register_blueprint(portaria_bp)
URL_BANCO = 'postgresql://neondb_owner:npg_F4Lr8SMQBqYy@ep-snowy-fog-ad66vpfz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def init_db():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS competidores (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            pontos INTEGER DEFAULT 0,
            vitorias INTEGER DEFAULT 0,
            derrotas INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batalhas_suico (
            id SERIAL PRIMARY KEY,
            round INTEGER NOT NULL,
            competidor1_id INTEGER REFERENCES competidores(id),
            competidor2_id INTEGER REFERENCES competidores(id),
            vencedor_id INTEGER,
            status TEXT DEFAULT 'pendente'
        )
    ''')

    conn.commit()
    conn.close()
init_db()
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome_completo = request.form.get('nome_completo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        try:
            conn = psycopg2.connect(URL_BANCO)
            cursor = conn.cursor()
            
            # 1. O Radar anti-duplicata (Busca se o email OU o nome já existem)
            cursor.execute('SELECT id FROM usuarios WHERE email = %s OR nome_completo = %s', (email, nome_completo))
            usuario_existente = cursor.fetchone()
            
            if usuario_existente:
                conn.close()
                return render_template('login.html', erro="Não foi possível cadastrar. Este e-mail ou nome já estão em uso.")

            # 2. Se o radar não apitou, cadastra o usuário
            cursor.execute('''
                INSERT INTO usuarios (nome_completo, email, senha, nivel_acesso) 
                VALUES (%s, %s, %s, 'comum')
            ''', (nome_completo, email, senha))
            
            conn.commit()
            conn.close()
            return redirect('/login')
            
        except Exception as e:
            return f" Erro ao tentar criar a conta: {e}"

    return render_template('cadastro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form.get('email')
        senha_digitada = request.form.get('senha')

        conn = psycopg2.connect(URL_BANCO)
        cursor = conn.cursor()
        
        try:
            # 1. Busca SÓ pelo email primeiro (trazendo a senha do banco junto pra c    onferir depois)
            cursor.execute('SELECT id, email, nivel_acesso, nome_completo, senha FROM usuarios WHERE email = %s', 
                           (email_digitado,))
            usuario = cursor.fetchone()
            
            if not usuario:
                # Se não achou ninguém com esse email:
                return render_template('login.html', erro="Essa conta não existe. Por favor, faça seu cadastro.")
            
            # 2. Se a conta existe, vamos conferir a senha (que está na posição 4 agora)
            senha_banco = usuario[4]
            
            if senha_digitada != senha_banco:
                # Se a senha não bater:
                return render_template('login.html', erro="Email ou senha incorretos.")
                
            # 3. Se passou pelos dois testes, faz o login!
            session['usuario_id'] = usuario[0] 
            session['usuario'] = usuario[1] 
            session['nivel_acesso'] = usuario[2]
            
            nome_banco = usuario[3]
            
            if nome_banco is None or str(nome_banco).strip() == "":
                return redirect('/completar_perfil')
            else:
                return redirect('/') 
                
        except Exception as e:
            print(f"Erro interno no login: {e}")
            return render_template('login.html', erro="Erro ao conectar com o banco.")
        finally:
            conn.close()

    return render_template('login.html')
@app.route('/completar_perfil', methods=['GET', 'POST'])
def completar_perfil():
    # Verifica se a pessoa realmente passou pelo login primeiro
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return redirect('/login')

    if request.method == 'POST':
        novo_nome = request.form.get('nome_completo')
        
        try:
            conn = psycopg2.connect(URL_BANCO)
            cursor = conn.cursor()
            # Atualiza o nome da pessoa no banco
            cursor.execute('UPDATE usuarios SET nome_completo = %s WHERE id = %s', (novo_nome, usuario_id))
            conn.commit()
            conn.close()
            
            # Se deu certo, libera a catraca pra página inicial!
            return redirect('/') 
            
        except Exception as e:
            # Se der erro no banco, mostra o erro na tela em vez de falhar em silêncio
            return f" Erro ao salvar o nome no banco de dados: {e}"

    return render_template('completar_perfil.html')
@app.route('/logout')
def logout():
    session.pop('usuario', None) 
    return redirect(url_for('home'))

@app.route('/ingressos')
def ingressos():
    if 'usuario' not in session:
        print("Acesso bloqueado: Tentativa de comprar ingresso sem login.")
        return redirect(url_for('login'))
    
    return render_template('ingressos.html')
@app.route('/cronograma')
def cronograma():
    return render_template('cronograma.html')



if __name__ == '__main__':
    init_db() # Executa a criação das tabelas antes de o site ir ao ar
    app.run(debug=True)