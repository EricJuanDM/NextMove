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

# ==========================================
# 1. ROTA DA AGENDA PÚBLICA (Com Coreografias)
# ==========================================
@app.route('/agenda')
def pagina_agenda():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    # Puxa os dados principais (O COALESCE evita que venha 'None' na tela)
    cursor.execute('''
        SELECT id, evento_nome, data_evento, COALESCE(tipo, 'EVENTO'), local, link_inscricao, COALESCE(origem_evento, 'PROPRIO') 
        FROM agenda WHERE data_evento >= CURRENT_DATE ORDER BY data_evento ASC
    ''')
    eventos_raw = cursor.fetchall()

    eventos_formatados = []
    for ev in eventos_raw:
        evento_dict = {
            'id': ev[0], 'nome': ev[1], 'data': ev[2], 'tipo': ev[3],
            'local': ev[4], 'link': ev[5], 'origem': ev[6], 'coreografias': []
        }
        
        # Se for competição, puxa a lista de coreografias do banco
        if evento_dict['origem'] == 'PARTICIPACAO':
            cursor.execute("SELECT nome_coreografia, modalidade FROM agenda_coreografias WHERE agenda_id = %s", (ev[0],))
            coreos = cursor.fetchall()
            for c in coreos:
                evento_dict['coreografias'].append({'nome': c[0], 'modalidade': c[1]})
                
        eventos_formatados.append(evento_dict)

    conn.close()
    return render_template('PUBLICA/agenda.html', eventos=eventos_formatados)


# ==========================================
# 2. ROTA PARA EDITAR EVENTOS NO ADMIN
# ==========================================
@app.route('/admin/agenda/editar/<int:id>', methods=['GET', 'POST'])
def editar_evento(id):
    if session.get('nivel_acesso') != 'superadmin': return redirect('/')
    
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('evento_nome')
        data = request.form.get('data_evento')
        tipo = request.form.get('tipo')
        origem = request.form.get('origem_evento')
        local = request.form.get('local')
        link = request.form.get('link')

        cursor.execute('''
            UPDATE agenda
            SET evento_nome=%s, data_evento=%s, tipo=%s, origem_evento=%s, local=%s, link_inscricao=%s
            WHERE id=%s
        ''', (nome, data, tipo, origem, local, link, id))

        # Resetar as coreografias e salvar as novas
        cursor.execute("DELETE FROM agenda_coreografias WHERE agenda_id = %s", (id,))
        
        if origem == 'PARTICIPACAO':
            nomes_coreos = request.form.getlist('coreo_nome[]')
            cats_coreos = request.form.getlist('coreo_cat[]')
            for n, c in zip(nomes_coreos, cats_coreos):
                if n.strip():
                    cursor.execute("INSERT INTO agenda_coreografias (agenda_id, nome_coreografia, modalidade) VALUES (%s, %s, %s)", (id, n, c))

        conn.commit()
        return redirect('/admin/agenda')

    # Para mostrar na tela os dados que já existem
    cursor.execute("SELECT * FROM agenda WHERE id = %s", (id,))
    evento = cursor.fetchone()
    cursor.execute("SELECT nome_coreografia, modalidade FROM agenda_coreografias WHERE agenda_id = %s", (id,))
    coreografias = cursor.fetchall()
    
    conn.close()
    return render_template('ADMINISTRACAO/agenda_editar.html', evento=evento, coreografias=coreografias)

# ROTA ADMIN: Formulário de Gerenciamento (Só Superadmin)
@app.route('/admin/agenda', methods=['GET', 'POST'])
def admin_agenda():
    if session.get('nivel_acesso') != 'superadmin': return redirect('/')
    
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    # Captura o ID de edição da URL (ex: /admin/agenda?edit_id=5)
    edit_id = request.args.get('edit_id')
    evento_editar = None
    coreografias_editar = []

    if request.method == 'POST':
        action = request.form.get('action') # Vamos usar um campo oculto para saber se é ADD ou EDIT
        
        nome = request.form.get('evento_nome')
        data = request.form.get('data_evento')
        tipo = request.form.get('tipo')
        origem = request.form.get('origem_evento')
        local = request.form.get('local')
        link = request.form.get('link')

        if action == 'add':
            cursor.execute('''
                INSERT INTO agenda (evento_nome, data_evento, tipo, origem_evento, local, link_inscricao)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            ''', (nome, data, tipo, origem, local, link))
            novo_id = cursor.fetchone()[0]
            
            if origem == 'PARTICIPACAO':
                nomes = request.form.getlist('coreo_nome[]')
                cats = request.form.getlist('coreo_cat[]')
                for n, c in zip(nomes, cats):
                    if n.strip():
                        cursor.execute("INSERT INTO agenda_coreografias (agenda_id, nome_coreografia, modalidade) VALUES (%s, %s, %s)", (novo_id, n, c))

        elif action == 'edit':
            id_atualizar = request.form.get('id_evento')
            cursor.execute('''
                UPDATE agenda SET evento_nome=%s, data_evento=%s, tipo=%s, origem_evento=%s, local=%s, link_inscricao=%s
                WHERE id=%s
            ''', (nome, data, tipo, origem, local, link, id_atualizar))
            
            cursor.execute("DELETE FROM agenda_coreografias WHERE agenda_id = %s", (id_atualizar,))
            if origem == 'PARTICIPACAO':
                nomes = request.form.getlist('coreo_nome[]')
                cats = request.form.getlist('coreo_cat[]')
                for n, c in zip(nomes, cats):
                    if n.strip():
                        cursor.execute("INSERT INTO agenda_coreografias (agenda_id, nome_coreografia, modalidade) VALUES (%s, %s, %s)", (id_atualizar, n, c))

        conn.commit()
        return redirect('/admin/agenda')

    # Se estivermos no modo de edição, busca os dados para o formulário de baixo
    if edit_id:
        cursor.execute("SELECT * FROM agenda WHERE id = %s", (edit_id,))
        evento_editar = cursor.fetchone()
        cursor.execute("SELECT nome_coreografia, modalidade FROM agenda_coreografias WHERE agenda_id = %s", (edit_id,))
        coreografias_editar = cursor.fetchall()

    cursor.execute("SELECT * FROM agenda ORDER BY data_evento DESC")
    todos_eventos = cursor.fetchall()
    conn.close()
    
    return render_template('ADMINISTRACAO/agenda_admin.html', 
                            eventos=todos_eventos, 
                            edit_mode=evento_editar, 
                            coreos_edit=coreografias_editar)

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