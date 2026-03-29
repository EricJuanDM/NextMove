import random
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify

# Criando o módulo do Torneio
votacao_bp = Blueprint('votacao_bp', __name__)

URL_BANCO = 'postgresql://neondb_owner:npg_F4Lr8SMQBqYy@ep-snowy-fog-ad66vpfz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'


# ==========================================
# 1. ROTAS DO PÚBLICO (BOLÃO / PALPITES)
# ==========================================

@votacao_bp.route('/batalhas')
def pagina_batalhas():
    # 🔒 TRAVA DE SEGURANÇA: Só quem fez login entra aqui!
    usuario_logado_id = session.get('usuario_id') 
    if not usuario_logado_id:
        return redirect('/login')

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT b.id, b.round, b.pool, b.status,
               c1.id, c1.nome, c2.id, c2.nome
        FROM batalhas_suico b
        JOIN competidores c1 ON b.competidor1_id = c1.id
        JOIN competidores c2 ON b.competidor2_id = c2.id
        ORDER BY b.round ASC, b.id ASC
    ''')
    batalhas = cursor.fetchall()

    meus_palpites = {}
    if usuario_logado_id:
        cursor.execute('SELECT batalha_id, palpite_vencedor_id FROM palpites WHERE usuario_id = %s', (usuario_logado_id,))
        votos_db = cursor.fetchall()
        meus_palpites = {voto[0]: voto[1] for voto in votos_db}

    conn.close()
    
    # IMPORTANTE: Verifique se o seu arquivo HTML se chama votacao.html ou batalhas.html e ajuste aqui se precisar!
    return render_template('votacao.html', batalhas=batalhas, meus_palpites=meus_palpites)


@votacao_bp.route('/ranking_bolao')
def ranking_bolao():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    # 👤 MUDANÇA AQUI: Trocamos u.email por u.nome_completo no SELECT e no GROUP BY
    cursor.execute('''
        SELECT COALESCE(u.nome_completo, 'Dançarino Sem Nome'), COUNT(p.id) as acertos
        FROM usuarios u
        JOIN palpites p ON u.id = p.usuario_id
        JOIN batalhas_suico b ON p.batalha_id = b.id
        WHERE b.status = 'finalizada' AND p.palpite_vencedor_id = b.vencedor_id
        GROUP BY u.nome_completo
        ORDER BY acertos DESC
    ''')
    ranking = cursor.fetchall()
    conn.close()
    
    return render_template('ranking.html', ranking=ranking)


@votacao_bp.route('/enviar_palpite/<int:batalha_id>/<int:competidor_id>', methods=['POST'])
def enviar_palpite(batalha_id, competidor_id):
    usuario_logado_id = session.get('usuario_id') 
    
    if not usuario_logado_id:
        return jsonify({'status': 'erro', 'mensagem': 'Você precisa fazer login para votar.'})

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT status FROM batalhas_suico WHERE id = %s", (batalha_id,))
        if cursor.fetchone()[0] == 'finalizada':
            return jsonify({'status': 'erro', 'mensagem': 'Batalha já encerrada!'})

        cursor.execute('''
            INSERT INTO palpites (usuario_id, batalha_id, palpite_vencedor_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario_id, batalha_id) 
            DO UPDATE SET palpite_vencedor_id = EXCLUDED.palpite_vencedor_id
        ''', (usuario_logado_id, batalha_id, competidor_id))
        
        conn.commit()
        return jsonify({'status': 'sucesso'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'erro', 'mensagem': str(e)})
    finally:
        conn.close()

@votacao_bp.route('/verificar_atualizacoes')
def verificar_atualizacoes():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM batalhas_suico')
    total = cursor.fetchone()[0]
    conn.close()
    return jsonify({'total_batalhas': total})


# ==========================================
# 2. ROTAS DO PAINEL ADMIN (GERENCIAMENTO)
# ==========================================

@votacao_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    # 🔒 TRAVA DE SEGURANÇA: Só admin entra no painel de gerenciar as chaves!
    nivel = session.get('nivel_acesso')
    if not nivel or nivel.lower() not in ['admin', 'superadmin']:
        return redirect('/')

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    if request.method == 'POST':
        nome_dancarino = request.form['nome']
        cursor.execute('INSERT INTO competidores (nome) VALUES (%s)', (nome_dancarino,))
        conn.commit()
        
    cursor.execute('SELECT * FROM competidores ORDER BY vitorias DESC, derrotas ASC')
    competidores = cursor.fetchall()

    cursor.execute('''
        SELECT b.id, b.round, 
               c1.id, c1.nome, c1.vitorias, c1.derrotas,
               c2.id, c2.nome, c2.vitorias, c2.derrotas,
               b.vencedor_id, b.status, b.pool
        FROM batalhas_suico b
        JOIN competidores c1 ON b.competidor1_id = c1.id
        JOIN competidores c2 ON b.competidor2_id = c2.id
        ORDER BY b.round ASC, b.id ASC
    ''')
    batalhas = cursor.fetchall()
    conn.close()
    
    return render_template('admin.html', competidores=competidores, batalhas=batalhas)


@votacao_bp.route('/gerar_batalhas_admin', methods=['POST'])
def gerar_batalhas_admin():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    cursor.execute('SELECT COALESCE(MAX(round), 0) + 1 FROM batalhas_suico')
    proximo_round = cursor.fetchone()[0]

    cursor.execute('SELECT id, vitorias, derrotas FROM competidores WHERE vitorias < 3 AND derrotas < 3')
    ativos = cursor.fetchall()

    if not ativos:
        conn.close()
        return redirect(url_for('votacao_bp.admin')) 

    grupos = {}
    for comp in ativos:
        score = f"{comp[1]}-{comp[2]}" 
        if score not in grupos: grupos[score] = []
        grupos[score].append(comp[0])

    for score, lista in grupos.items():
        random.shuffle(lista) 
        for i in range(0, len(lista) - 1, 2):
            comp1_id = lista[i]
            comp2_id = lista[i+1]

            cursor.execute('''
                INSERT INTO batalhas_suico (round, competidor1_id, competidor2_id, pool) 
                VALUES (%s, %s, %s, %s)
            ''', (proximo_round, comp1_id, comp2_id, score))
    
    conn.commit()
    conn.close()
    return redirect(url_for('votacao_bp.admin'))


@votacao_bp.route('/gerar_mata_mata', methods=['POST'])
def gerar_mata_mata():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT pool FROM batalhas_suico WHERE pool IN ('Quartas', 'Semi', 'Final')")
    pools = [row[0] for row in cursor.fetchall()]

    if 'Quartas' not in pools:
        cursor.execute("SELECT id FROM competidores WHERE vitorias >= 3 LIMIT 8")
        classificados = [row[0] for row in cursor.fetchall()]
        
        if len(classificados) == 8:
            random.shuffle(classificados) 
            for i in range(0, 8, 2):
                cursor.execute('''INSERT INTO batalhas_suico (round, competidor1_id, competidor2_id, pool) 
                                  VALUES (6, %s, %s, 'Quartas')''', (classificados[i], classificados[i+1]))
    
    elif 'Semi' not in pools:
        cursor.execute("SELECT vencedor_id FROM batalhas_suico WHERE pool = 'Quartas' AND status = 'finalizada'")
        vencedores = [row[0] for row in cursor.fetchall()]
        
        if len(vencedores) == 4:
            for i in range(0, 4, 2):
                cursor.execute('''INSERT INTO batalhas_suico (round, competidor1_id, competidor2_id, pool) 
                                  VALUES (7, %s, %s, 'Semi')''', (vencedores[i], vencedores[i+1]))
    
    elif 'Final' not in pools:
        cursor.execute("SELECT vencedor_id FROM batalhas_suico WHERE pool = 'Semi' AND status = 'finalizada'")
        vencedores = [row[0] for row in cursor.fetchall()]
        
        if len(vencedores) == 2:
            cursor.execute('''INSERT INTO batalhas_suico (round, competidor1_id, competidor2_id, pool) 
                              VALUES (8, %s, %s, 'Final')''', (vencedores[0], vencedores[1]))

    conn.commit()
    conn.close()
    return redirect(url_for('votacao_bp.admin'))


@votacao_bp.route('/vitoria/<int:batalha_id>/<int:vencedor_id>', methods=['POST'])
def registrar_vitoria(batalha_id, vencedor_id):
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    cursor.execute("SELECT competidor1_id, competidor2_id FROM batalhas_suico WHERE id = %s", (batalha_id,))
    c1, c2 = cursor.fetchone()
    perdedor_id = c2 if vencedor_id == c1 else c1

    cursor.execute("UPDATE batalhas_suico SET vencedor_id = %s, status = 'finalizada' WHERE id = %s", (vencedor_id, batalha_id))
    cursor.execute("UPDATE competidores SET pontos = pontos + 3, vitorias = vitorias + 1 WHERE id = %s", (vencedor_id,))
    cursor.execute("UPDATE competidores SET derrotas = derrotas + 1 WHERE id = %s", (perdedor_id,))

    conn.commit()
    conn.close()
    
    return jsonify({'status': 'sucesso'})


@votacao_bp.route('/deletar_competidor/<int:id>')
def deletar_competidor(id):
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM competidores WHERE id = %s', (id,))
        conn.commit()
    except:
        conn.rollback()
    
    conn.close()
    return redirect(url_for('votacao_bp.admin'))


@votacao_bp.route('/resetar_torneio', methods=['POST'])
def resetar_torneio():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM palpites') 
    cursor.execute('DELETE FROM batalhas_suico')
    cursor.execute('DELETE FROM competidores')
    cursor.execute('ALTER SEQUENCE batalhas_suico_id_seq RESTART WITH 1')
    cursor.execute('ALTER SEQUENCE competidores_id_seq RESTART WITH 1')

    conn.commit()
    conn.close()
    return redirect(url_for('votacao_bp.admin'))