from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
# O Flask exige uma chave secreta para usar sessões de forma segura
app.secret_key = 'chave_secreta_next_move' 

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
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    # Passamos a página principal normalmente, o HTML vai ler a sessão sozinho
    return render_template('index.html')

@app.route('/ingressos')
def ingressos():
    return render_template('ingressos.html')

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
        
        # SUCESSO! Salva o e-mail na sessão (entrega o crachá)
        session['usuario'] = email_digitado
        return redirect(url_for('home')) # Manda direto pra Home já logado!
        
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
            # SUCESSO! Salva o e-mail na sessão
            session['usuario'] = email_digitado
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro="Dados incorretos")
            
    return render_template('login.html')

# Rota para Sair da conta (apagar o crachá)
@app.route('/logout')
def logout():
    session.pop('usuario', None) # Apaga a sessão
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)