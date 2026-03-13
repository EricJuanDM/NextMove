import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session

from votacao import votacao_bp

app = Flask(__name__)
app.secret_key = 'chave_secreta_next_move' 
app.register_blueprint(votacao_bp)

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
        email_digitado = request.form.get('email')
        senha_digitada = request.form.get('senha')
        
        conn = psycopg2.connect(URL_BANCO)
        cursor = conn.cursor()
        
        # É VITAL puxar o 'id' na busca do banco
        cursor.execute('SELECT id, email FROM usuarios WHERE email = %s AND senha = %s', (email_digitado, senha_digitada))
        usuario = cursor.fetchone()
        conn.close()
        
        if usuario:
            # ⚠️ O SEGREDO ESTÁ AQUI: Salvar o ID (posição 0) na sessão com o nome 'usuario_id'
            session['usuario_id'] = usuario[0]  
            session['usuario'] = usuario[1] # (Opcional) Salva o email também se quiser
            
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro="Senha incorreta")

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




if __name__ == '__main__':
    init_db() # Executa a criação das tabelas antes de o site ir ao ar
    app.run(debug=True)