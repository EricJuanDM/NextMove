import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
# Importando as "Gavetas" (Blueprints)
from votacao import votacao_bp
from portaria import portaria_bp

app = Flask(__name__)
app.secret_key = 'chave_secreta_next_move' 

# Ligando as gavetas no app principal
app.register_blueprint(votacao_bp)
app.register_blueprint(portaria_bp)

URL_BANCO = 'postgresql://neondb_owner:npg_F4Lr8SMQBqYy@ep-snowy-fog-ad66vpfz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def init_db():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome_completo TEXT,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            nivel_acesso TEXT DEFAULT 'comum'
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

# Cria as tabelas logo que o arquivo é lido
init_db()

@app.route('/')
def home():
    return render_template('PUBLICA/index.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome_completo = request.form.get('nome_completo')
        email = request.form.get('email').strip().lower() # Sanitização!
        senha = request.form.get('senha')
        
        try:
            conn = psycopg2.connect(URL_BANCO)
            cursor = conn.cursor()
            
            # 1. O Radar anti-duplicata
            cursor.execute('SELECT id FROM usuarios WHERE email = %s OR nome_completo = %s', (email, nome_completo))
            usuario_existente = cursor.fetchone()
            
            if usuario_existente:
                conn.close()
                return render_template('PUBLICA/login.html', erro="Não foi possível cadastrar. Este e-mail ou nome já estão em uso.")

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

    return render_template('PUBLICA/cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form.get('email').strip().lower() # Sanitização!
        senha_digitada = request.form.get('senha')

        conn = psycopg2.connect(URL_BANCO)
        cursor = conn.cursor()
        
        try:
            # 1. Busca SÓ pelo email primeiro 
            cursor.execute('SELECT id, email, nivel_acesso, nome_completo, senha FROM usuarios WHERE email = %s', (email_digitado,))
            usuario = cursor.fetchone()
            
            if not usuario:
                return render_template('PUBLICA/login.html', erro="Essa conta não existe. Por favor, faça seu cadastro.")
            
            # 2. Conferir a senha
            senha_banco = usuario[4]
            if senha_digitada != senha_banco:
                return render_template('PUBLICA/login.html', erro="Email ou senha incorretos.")
                
            # 3. Faz o login!
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
            return render_template('PUBLICA/login.html', erro="Erro ao conectar com o banco.")
        finally:
            conn.close()

    return render_template('PUBLICA/login.html')

@app.route('/completar_perfil', methods=['GET', 'POST'])
def completar_perfil():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return redirect('/login')

    if request.method == 'POST':
        novo_nome = request.form.get('nome_completo')
        try:
            conn = psycopg2.connect(URL_BANCO)
            cursor = conn.cursor()
            cursor.execute('UPDATE usuarios SET nome_completo = %s WHERE id = %s', (novo_nome, usuario_id))
            conn.commit()
            conn.close()
            return redirect('/') 
        except Exception as e:
            return f" Erro ao salvar o nome no banco de dados: {e}"

    return render_template('PUBLICA/completar_perfil.html')

@app.route('/logout')
def logout():
    session.clear() # Limpa toda a sessão de uma vez para evitar bugs
    return redirect(url_for('home'))

@app.route('/ingressos')
def ingressos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('EVENTO/ingressos.html')

@app.route('/cronograma')
def cronograma():
    return render_template('EVENTO/cronograma.html')

@app.route('/meus_ingressos')
def meus_ingressos():
    if 'usuario_id' not in session:
        return redirect('/login')
    
    usuario_id = session['usuario_id']
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT tipo_ingresso, checkin_realizado 
            FROM ingressos 
            WHERE usuario_id = %s
            ORDER BY checkin_realizado ASC, tipo_ingresso ASC
        ''', (usuario_id,))
        ingressos = cursor.fetchall()
        return render_template('EVENTO/meus_ingressos.html', ingressos=ingressos)
    except Exception as e:
        return f"Erro ao buscar ingressos: {e}"
    finally:
        conn.close()

# ROTA PÚBLICA: Onde todos veem a agenda
@app.route('/agenda')
def pagina_agenda():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    # O SELECT * garante que as novas colunas (origem e subcategoria) também venham para o HTML!
    cursor.execute("SELECT * FROM agenda WHERE data_evento >= CURRENT_DATE ORDER BY data_evento ASC")
    eventos_db = cursor.fetchall()
    
    conn.close()
    return render_template('PUBLICA/agenda.html', eventos=eventos_db)

# ROTA ADMIN: Formulário de Gerenciamento (Só Superadmin)
@app.route('/admin/agenda', methods=['GET', 'POST'])
def admin_agenda():
    nivel = session.get('nivel_acesso')
    if nivel != 'superadmin': 
        return redirect('/')

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('evento_nome')
        data = request.form.get('data_evento')
        tipo = request.form.get('tipo')
        local = request.form.get('local')
        link = request.form.get('link')

        cursor.execute('''
            INSERT INTO agenda (evento_nome, data_evento, tipo, local, link_inscricao)
            VALUES (%s, %s, %s, %s, %s)
        ''', (nome, data, tipo, local, link))
        conn.commit()
        return redirect('/admin/agenda')

    cursor.execute("SELECT * FROM agenda ORDER BY data_evento DESC")
    todos_eventos = cursor.fetchall()
    conn.close()
    
    return render_template('ADMINISTRACAO/agenda_admin.html', eventos=todos_eventos)

# ROTA PARA DELETAR EVENTO
@app.route('/admin/agenda/deletar/<int:id>')
def deletar_evento(id):
    if session.get('nivel_acesso') != 'superadmin': return redirect('/')
    
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agenda WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin/agenda')

# --- ROTAS DO HALL DA FAMA ---

@app.route('/titulos')
def titulos():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, colocacao, categoria, ano, descricao FROM conquistas ORDER BY ano DESC")
    conquistas_db = cursor.fetchall()
    conn.close()
    return render_template('PUBLICA/titulos.html', conquistas=conquistas_db)

@app.route('/admin/conquistas', methods=['GET', 'POST'])
def admin_conquistas():
    if session.get('nivel_acesso') != 'superadmin': return redirect('/')
    
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        colocacao = request.form.get('colocacao')
        categoria = request.form.get('categoria')
        ano = request.form.get('ano')
        descricao = request.form.get('descricao')

        cursor.execute('''
            INSERT INTO conquistas (titulo, colocacao, categoria, ano, descricao)
            VALUES (%s, %s, %s, %s, %s)
        ''', (titulo, colocacao, categoria, ano, descricao))
        conn.commit()
        return redirect('/admin/conquistas')

    cursor.execute("SELECT * FROM conquistas ORDER BY ano DESC")
    todas = cursor.fetchall()
    conn.close()
    return render_template('ADMINISTRACAO/conquistas_admin.html', conquistas=todas)

@app.route('/admin/conquistas/deletar/<int:id>')
def deletar_conquista(id):
    if session.get('nivel_acesso') != 'superadmin': return redirect('/')
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conquistas WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin/conquistas')

if __name__ == '__main__':
    app.run(debug=True)