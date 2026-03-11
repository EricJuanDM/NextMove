from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import random

app = Flask(__name__)
app.secret_key = 'chave_secreta_next_move' 

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
        email = request.form['email']
        senha = request.form['senha']
        
        try:
            conn = psycopg2.connect(URL_BANCO)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO usuarios (email, senha) VALUES (%s, %s)', (email, senha))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            return "Esse e-mail já está cadastrado!"
            
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = psycopg2.connect(URL_BANCO)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE email = %s AND senha = %s', (email, senha))
        usuario = cursor.fetchone()
        conn.close()
        
        if usuario:
            session['usuario'] = usuario[1] 
            return redirect(url_for('home'))
        else:
            return "E-mail ou senha incorretos!"
            
    return render_template('login.html')

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


@app.route('/batalhas')
def batalhas():
    return render_template('batalhas.html')


# ==========================================
# ROTAS DO SISTEMA SUÍÇO (PAINEL ADMIN)
# ==========================================

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # Proteção: só entra se estiver logado
    if 'usuario' not in session: 
        return redirect(url_for('login'))
        
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    # 1. Adicionar novo competidor (via formulário do admin)
    if request.method == 'POST':
        nome_dancarino = request.form['nome']
        cursor.execute('INSERT INTO competidores (nome) VALUES (%s)', (nome_dancarino,))
        conn.commit()
        
    # 2. Puxa os competidores cadastrados
    cursor.execute('SELECT * FROM competidores ORDER BY pontos DESC, vitorias DESC')
    competidores = cursor.fetchall()

    # 3. Puxa o histórico de batalhas desenhadas (Round a Round)
    cursor.execute('''
        SELECT b.id, b.round, 
               c1.id, c1.nome, c1.vitorias, c1.derrotas,
               c2.id, c2.nome, c2.vitorias, c2.derrotas,
               b.vencedor_id, b.status
        FROM batalhas_suico b
        JOIN competidores c1 ON b.competidor1_id = c1.id
        JOIN competidores c2 ON b.competidor2_id = c2.id
        ORDER BY b.round ASC, b.id ASC
    ''')
    batalhas = cursor.fetchall()
    conn.close()
    
    return render_template('admin.html', competidores=competidores, batalhas=batalhas)


@app.route('/gerar_batalhas', methods=['POST'])
def gerar_batalhas():
    if 'usuario' not in session: return redirect(url_for('login'))

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    # Descobre qual é o round atual
    cursor.execute('SELECT COALESCE(MAX(round), 0) + 1 FROM batalhas_suico')
    proximo_round = cursor.fetchone()[0]

    # Puxa a galera ordenada pela pontuação para garantir o nivelamento
    cursor.execute('SELECT id FROM competidores ORDER BY pontos DESC')
    competidores = [linha[0] for linha in cursor.fetchall()]

    # No Round 1, embaralha todo mundo para o sorteio inicial ser 100% aleatório
    if proximo_round == 1:
        random.shuffle(competidores)

    # Forma as chaves (de 2 em 2)
    for i in range(0, len(competidores) - 1, 2):
        comp1_id = competidores[i]
        comp2_id = competidores[i+1]

        cursor.execute('''
            INSERT INTO batalhas_suico (round, competidor1_id, competidor2_id) 
            VALUES (%s, %s, %s)
        ''', (proximo_round, comp1_id, comp2_id))

    conn.commit()
    conn.close()
    return redirect(url_for('admin'))


@app.route('/vitoria/<int:batalha_id>/<int:vencedor_id>')
def registrar_vitoria(batalha_id, vencedor_id):
    if 'usuario' not in session: return redirect(url_for('login'))

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    # Descobre quem perdeu a batalha para atualizar o status dele também
    cursor.execute("SELECT competidor1_id, competidor2_id FROM batalhas_suico WHERE id = %s", (batalha_id,))
    c1, c2 = cursor.fetchone()
    perdedor_id = c2 if vencedor_id == c1 else c1

    # Atualiza a batalha registrando o vencedor
    cursor.execute("UPDATE batalhas_suico SET vencedor_id = %s, status = 'finalizada' WHERE id = %s", (vencedor_id, batalha_id))
    
    # Dá 3 pontos e 1 vitória para o ganhador
    cursor.execute("UPDATE competidores SET pontos = pontos + 3, vitorias = vitorias + 1 WHERE id = %s", (vencedor_id,))
    
    # Dá 1 derrota para quem perdeu
    cursor.execute("UPDATE competidores SET derrotas = derrotas + 1 WHERE id = %s", (perdedor_id,))

    conn.commit()
    conn.close()
    return redirect(url_for('admin'))


@app.route('/deletar_competidor/<int:id>')
def deletar_competidor(id):
    if 'usuario' not in session: return redirect(url_for('login'))

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM competidores WHERE id = %s', (id,))
        conn.commit()
    except Exception as e:
        conn.rollback() # Evita crash no servidor se você tentar deletar alguém que já está no meio do torneio
    
    conn.close()
    return redirect(url_for('admin'))


# ==========================================
# INICIAR O SERVIDOR
# ==========================================
if __name__ == '__main__':
    init_db() # Executa a criação das tabelas antes de o site ir ao ar
    app.run(debug=True)