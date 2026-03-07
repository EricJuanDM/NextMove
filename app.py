from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'chave_secreta_next_move' 

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('nextmove.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batalhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dancarino_a TEXT NOT NULL,
            dancarino_b TEXT NOT NULL,
            status TEXT DEFAULT 'ativa'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_email TEXT NOT NULL,
            batalha_id INTEGER NOT NULL,
            escolha TEXT NOT NULL,
            UNIQUE(usuario_email, batalha_id)
        )
    ''')
    
    # Insere as batalhas de teste se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM batalhas")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO batalhas (dancarino_a, dancarino_b) VALUES (?, ?)", ("Luigi", "Davi"))
        cursor.execute("INSERT INTO batalhas (dancarino_a, dancarino_b) VALUES (?, ?)", ("Sol", "Armanda"))
        print("Batalhas de teste criadas no banco!")

    conn.commit()
    conn.close()

init_db()

# --- NOSSAS ROTAS ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ingressos')
def ingressos():
    return render_template('ingressos.html')

@app.route('/cronograma')
def cronograma():
    return render_template('cronograma.html')

@app.route('/cadastro', methods=['POST'])
def cadastro():
    email_digitado = request.form['email']
    senha_digitada = request.form['senha']
    
    try:
        conn = sqlite3.connect('nextmove.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (email, senha) VALUES (?, ?)", (email_digitado, senha_digitada))
        conn.commit()
        conn.close()
        
        session['usuario'] = email_digitado
        return redirect(url_for('home'))
        
    except sqlite3.IntegrityError:
        print("ERRO: E-mail já existe.")
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form['email']
        senha_digitada = request.form['senha']
        
        conn = sqlite3.connect('nextmove.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ? AND senha = ?", (email_digitado, senha_digitada))
        usuario = cursor.fetchone()
        conn.close()
        
        if usuario:
            session['usuario'] = email_digitado
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro="Dados incorretos")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('home'))

# --- ROTA DA ARENA DE BATALHAS ---
@app.route('/batalhas')
def batalhas():
    # Verifica se a pessoa tem o crachá de login
    if 'usuario' not in session:
        print("Acesso negado: Usuário não logado tentou acessar as batalhas.")
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('nextmove.db')
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM batalhas WHERE status = 'ativa'")
    batalhas_ativas = cursor.fetchall()
    conn.close()
    
    return render_template('batalhas.html', batalhas=batalhas_ativas)

if __name__ == '__main__':
    app.run(debug=True)