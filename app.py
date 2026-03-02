from flask import Flask, render_template, request, redirect, url_for
import sqlite3 # Importamos o banco de dados nativo do Python

app = Flask(__name__)

# Função para inicializar o banco de dados
def init_db():
    conn = sqlite3.connect('NextMove.db')
    cursor = conn.cursor()
    # Criando a tabela com SQL puro
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Executa a função logo que o app inicia
init_db()

# ... (aqui continuam as suas rotas @app.route que já criamos) ...

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form['email']
        senha_digitada = request.form['senha']
        
        # Conecta no banco e insere o novo usuário
        try:
            conn = sqlite3.connect('nextmove.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO usuarios (email, senha) VALUES (?, ?)", (email_digitado, senha_digitada))
            conn.commit()
            conn.close()
            
            print(f"Usuário {email_digitado} cadastrado com sucesso no banco!")
            return redirect(url_for('home'))
            
        except sqlite3.IntegrityError:
            print("Erro: Esse e-mail já está cadastrado.")
            return render_template('login.html', erro="E-mail já existe!")
            
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)