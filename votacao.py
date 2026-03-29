import random
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify

votacao_bp = Blueprint('votacao_bp', __name__)
URL_BANCO = 'postgresql://neondb_owner:npg_F4Lr8SMQBqYy@ep-snowy-fog-ad66vpfz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

# ==========================================
# O MOTOR DA DUPLA ELIMINAÇÃO (STATE MACHINE)
# ==========================================
# 'c1' significa que entra na vaga 1 da próxima batalha. 'c2' na vaga 2.
REGRAS_AVANCO = {
    'W1': {'win': ('W5', 'c1'), 'lose': ('L1', 'c1')},
    'W2': {'win': ('W5', 'c2'), 'lose': ('L1', 'c2')},
    'W3': {'win': ('W6', 'c1'), 'lose': ('L2', 'c1')},
    'W4': {'win': ('W6', 'c2'), 'lose': ('L2', 'c2')},
    'W5': {'win': ('W7', 'c1'), 'lose': ('L4', 'c1')}, # Cruzamento: Perdedor da chave de cima vai pra de baixo invertido
    'W6': {'win': ('W7', 'c2'), 'lose': ('L3', 'c1')}, # Cruzamento
    'L1': {'win': ('L3', 'c2'), 'lose': None},
    'L2': {'win': ('L4', 'c2'), 'lose': None},
    'L3': {'win': ('L5', 'c1'), 'lose': None},
    'L4': {'win': ('L5', 'c2'), 'lose': None},
    'L5': {'win': ('L6', 'c1'), 'lose': None},
    'W7': {'win': ('GF1', 'c1'), 'lose': ('L6', 'c2')}, # Final dos Vencedores
    'L6': {'win': ('GF1', 'c2'), 'lose': None},         # Final da Repescagem
    'GF1': {'win': 'FIM', 'lose': 'RESET'}              # Grande Final
}

# ==========================================
# ROTAS DO PAINEL ADMIN
# ==========================================

@votacao_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    nivel = session.get('nivel_acesso')
    if not nivel or nivel.lower() not in ['admin', 'superadmin']: return redirect('/')

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        cursor.execute('INSERT INTO competidores (nome) VALUES (%s)', (nome,))
        conn.commit()
        
    cursor.execute('SELECT * FROM competidores ORDER BY id ASC')
    competidores = cursor.fetchall()

    cursor.execute('''
        SELECT b.id, b.pool, b.status, b.vencedor_id,
               c1.id, c1.nome, c2.id, c2.nome
        FROM batalhas_suico b
        LEFT JOIN competidores c1 ON b.competidor1_id = c1.id
        LEFT JOIN competidores c2 ON b.competidor2_id = c2.id
        ORDER BY b.id ASC
    ''')
    batalhas = cursor.fetchall()
    conn.close()
    
    return render_template('admin.html', competidores=competidores, batalhas=batalhas)

@votacao_bp.route('/gerar_bracket_8', methods=['POST'])
def gerar_bracket_8():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    # Agora puxamos o ID e o NOME para o Python poder separar os cabeças de chave
    cursor.execute('SELECT id, nome FROM competidores')
    todos_competidores = cursor.fetchall()

    if len(todos_competidores) != 8:
        conn.close()
        return "Erro: Você precisa de EXATAMENTE 8 competidores cadastrados para gerar esta chave.", 400

    # 1. A LISTA VIP: O Python vai procurar quem tem esses nomes
    nomes_vips = ['igor', 'felipe vermelho', 'emily vaz', 'marco antonio']
    
    cabecas_de_chave = []
    outros_competidores = []

    # 2. SEPARANDO A GALERA
    for comp in todos_competidores:
        comp_id = comp[0]
        comp_nome = comp[1].lower().strip() # Deixa tudo minúsculo para facilitar a busca
        
        # Checa se o nome digitado tem algum dos nomes VIPs no meio
        is_vip = any(vip in comp_nome for vip in nomes_vips)
        
        if is_vip:
            cabecas_de_chave.append(comp_id)
        else:
            outros_competidores.append(comp_id)

    # 3. O SORTEIO INTELIGENTE
    # Trava de segurança: Se você digitou o nome de alguém diferente e não achou os 4 exatos, ele sorteia 100% aleatório para não travar o evento
    if len(cabecas_de_chave) != 4 or len(outros_competidores) != 4:
        ativos = [c[0] for c in todos_competidores]
        random.shuffle(ativos)
    else:
        # Embaralha os VIPs entre si, e os Outros entre si
        random.shuffle(cabecas_de_chave)
        random.shuffle(outros_competidores)
        
        # Monta a lista final colocando: [VIP, Outro, VIP, Outro, VIP, Outro, VIP, Outro]
        ativos = [
            cabecas_de_chave[0], outros_competidores[0], # Luta W1
            cabecas_de_chave[1], outros_competidores[1], # Luta W2
            cabecas_de_chave[2], outros_competidores[2], # Luta W3
            cabecas_de_chave[3], outros_competidores[3]  # Luta W4
        ]

    # Cria todas as 14 batalhas da chave
    pools_iniciais = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'GF1']
    
    for pool in pools_iniciais:
        if pool == 'W1': cursor.execute('INSERT INTO batalhas_suico (pool, competidor1_id, competidor2_id, round) VALUES (%s, %s, %s, 1)', (pool, ativos[0], ativos[1]))
        elif pool == 'W2': cursor.execute('INSERT INTO batalhas_suico (pool, competidor1_id, competidor2_id, round) VALUES (%s, %s, %s, 1)', (pool, ativos[2], ativos[3]))
        elif pool == 'W3': cursor.execute('INSERT INTO batalhas_suico (pool, competidor1_id, competidor2_id, round) VALUES (%s, %s, %s, 1)', (pool, ativos[4], ativos[5]))
        elif pool == 'W4': cursor.execute('INSERT INTO batalhas_suico (pool, competidor1_id, competidor2_id, round) VALUES (%s, %s, %s, 1)', (pool, ativos[6], ativos[7]))
        else: cursor.execute('INSERT INTO batalhas_suico (pool, round) VALUES (%s, 1)', (pool,))
    
    conn.commit()
    conn.close()
    return redirect(url_for('votacao_bp.admin'))

@votacao_bp.route('/vitoria/<int:batalha_id>/<int:vencedor_id>', methods=['POST'])
def registrar_vitoria(batalha_id, vencedor_id):
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()

    cursor.execute("SELECT pool, competidor1_id, competidor2_id FROM batalhas_suico WHERE id = %s", (batalha_id,))
    pool, c1, c2 = cursor.fetchone()
    perdedor_id = c2 if vencedor_id == c1 else c1

    # Atualiza a batalha atual como finalizada
    cursor.execute("UPDATE batalhas_suico SET vencedor_id = %s, status = 'finalizada' WHERE id = %s", (vencedor_id, batalha_id))

    regras = REGRAS_AVANCO.get(pool)
    if regras:
        # Lógica do Vencedor
        if regras['win'] not in ['FIM', 'RESET']:
            prox_pool_win, vaga_win = regras['win']
            coluna_win = 'competidor1_id' if vaga_win == 'c1' else 'competidor2_id'
            cursor.execute(f"UPDATE batalhas_suico SET {coluna_win} = %s WHERE pool = %s", (vencedor_id, prox_pool_win))
        
        # Lógica do Perdedor
        if regras['lose'] not in [None, 'CHECK_RESET', 'RESET']:
            prox_pool_lose, vaga_lose = regras['lose']
            coluna_lose = 'competidor1_id' if vaga_lose == 'c1' else 'competidor2_id'
            cursor.execute(f"UPDATE batalhas_suico SET {coluna_lose} = %s WHERE pool = %s", (perdedor_id, prox_pool_lose))

        # A Regra Mágica do Reset na Grande Final!
        if pool == 'GF1':
            if vencedor_id == c2:
                cursor.execute('INSERT INTO batalhas_suico (pool, competidor1_id, competidor2_id, round) VALUES (%s, %s, %s, 2)', ('GF2', c1, c2))

    conn.commit()
    conn.close()
    return jsonify({'status': 'sucesso'})

@votacao_bp.route('/deletar_competidor/<int:id>')
def deletar_competidor(id):
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM competidores WHERE id = %s', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('votacao_bp.admin'))

@votacao_bp.route('/resetar_torneio', methods=['POST'])
def resetar_torneio():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM palpites') 
    cursor.execute('DELETE FROM batalhas_suico')
    cursor.execute('DELETE FROM competidores')
    conn.commit()
    conn.close()
    return redirect(url_for('votacao_bp.admin'))

# ==========================================
# ROTAS PÚBLICAS (VISÃO DA GALERA E BOLÃO)
# ==========================================

@votacao_bp.route('/votacao')
def pagina_batalhas():
    usuario_logado_id = session.get('usuario_id') 
    if not usuario_logado_id: return redirect('/login')

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    cursor.execute('''SELECT b.id, b.pool, b.status, b.vencedor_id, c1.id, c1.nome, c2.id, c2.nome 
                      FROM batalhas_suico b 
                      LEFT JOIN competidores c1 ON b.competidor1_id = c1.id 
                      LEFT JOIN competidores c2 ON b.competidor2_id = c2.id 
                      ORDER BY b.id ASC''')
    batalhas = cursor.fetchall()
    
    cursor.execute('SELECT batalha_id, palpite_vencedor_id FROM palpites WHERE usuario_id = %s', (usuario_logado_id,))
    meus_palpites = {voto[0]: voto[1] for voto in cursor.fetchall()}
    conn.close()
    
    # Aqui renderizamos o HTML que fizemos na mensagem anterior!
    return render_template('votacao.html', batalhas=batalhas, meus_palpites=meus_palpites)

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

@votacao_bp.route('/ranking_bolao')
def ranking_bolao():
    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    
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