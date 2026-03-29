from flask import Blueprint, render_template, request, redirect, session, jsonify
import psycopg2

# Cria o "módulo" da portaria
portaria_bp = Blueprint('portaria', __name__)
URL_BANCO = 'postgresql://neondb_owner:npg_F4Lr8SMQBqYy@ep-snowy-fog-ad66vpfz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'


@portaria_bp.route('/portaria')
def painel_portaria():
    nivel = session.get('nivel_acesso')
    if nivel not in ['admin', 'superadmin']:
        return redirect('/')
    return render_template('portaria/portaria.html', nivel=nivel)

@portaria_bp.route('/venda_porta', methods=['GET', 'POST'])
def venda_porta():
    if session.get('nivel_acesso') not in ['admin', 'superadmin']:
        return redirect('/')

    if request.method == 'POST':
        nome_comprador = request.form.get('nome_completo')
        tipo_ingresso = request.form.get('tipo_ingresso')
        email = request.form.get('email').strip().lower()
        import random
        email_gerado = f"porta_{random.randint(10000, 99999)}@nextmove.local"
        
        conn = psycopg2.connect(URL_BANCO)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO usuarios (nome_completo, email, senha, nivel_acesso) VALUES (%s, %s, %s, %s) RETURNING id', 
                        (nome_comprador, email_gerado, 'venda_porta', 'comum'))
            novo_usuario_id = cursor.fetchone()[0]
            
            if tipo_ingresso == 'aula_1': ingressos_reais = ['aula_1', 'espectador']
            elif tipo_ingresso == 'aula_2': ingressos_reais = ['aula_2', 'espectador']
            elif tipo_ingresso == 'pacote_aulas': ingressos_reais = ['aula_1', 'aula_2', 'espectador']
            elif tipo_ingresso == 'competidor': ingressos_reais = ['batalhas', 'espectador']
            else: ingressos_reais = ['espectador']
            
            # Gera os cupons separados (já com check-in TRUE porque é na porta)
            for ing in ingressos_reais:
                    cursor.execute('SELECT id FROM ingressos WHERE usuario_id = %s AND tipo_ingresso = %s', (usuario_id, ing))
                    ingresso_ja_existe = cursor.fetchone()
                    
                    if not ingresso_ja_existe:
                        cursor.execute('INSERT INTO ingressos (usuario_id, tipo_ingresso, checkin_realizado) VALUES (%s, %s, FALSE)', (usuario_id, ing))
                
                
            conn.commit()
            return render_template('venda_porta.html', mensagem_sucesso=f"Venda registrada! {nome_comprador} já está com check-in feito.")
        except Exception as e:
            conn.rollback()
            return render_template('portaria/venda_porta.html', erro=str(e))
        finally:
            conn.close()

    return render_template('portaria/venda_porta.html')

@portaria_bp.route('/checkin/<tipo_lista>')
def pagina_checkin(tipo_lista):
    if session.get('nivel_acesso') not in ['admin', 'superadmin']:
        return redirect('/')

    regras_listas = {
        'aula_1': ['aula_1'],
        'aula_2': ['aula_2'],
        'batalhas': ['batalhas'],
        'evento_geral': ['espectador']
    }
    tipos_permitidos = regras_listas.get(tipo_lista, [])

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    try:
        query = '''
            SELECT i.id, u.nome_completo, i.tipo_ingresso, i.checkin_realizado 
            FROM ingressos i
            JOIN usuarios u ON i.usuario_id = u.id
            WHERE i.tipo_ingresso = ANY(%s)
            ORDER BY u.nome_completo ASC
        '''
        cursor.execute(query, (tipos_permitidos,))
        lista_participantes = cursor.fetchall()
    except Exception as e:
        return f"Erro ao buscar lista: {e}"
    finally:
        conn.close()

    titulos = {
        'aula_1': 'Check-in: Aula 1', 'aula_2': 'Check-in: Aula 2',
        'batalhas': 'Check-in: Competidores', 'evento_geral': 'Entrada Geral do Evento'
    }
    titulo_pagina = titulos.get(tipo_lista, 'Lista de Check-in')

    return render_template('portaria/checkin.html', participantes=lista_participantes, titulo=titulo_pagina)

@portaria_bp.route('/api/confirmar_checkin/<int:ingresso_id>', methods=['POST'])
def confirmar_checkin(ingresso_id):
    if session.get('nivel_acesso') not in ['admin', 'superadmin']:
        return jsonify({'status': 'erro', 'mensagem': 'Sem permissão'})

    conn = psycopg2.connect(URL_BANCO)
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE ingressos SET checkin_realizado = TRUE WHERE id = %s', (ingresso_id,))
        conn.commit()
        return jsonify({'status': 'sucesso'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'erro', 'mensagem': str(e)})
    finally:
        conn.close()
@portaria_bp.route('/venda_antecipada', methods=['GET', 'POST'])
def venda_antecipada():
    # Segurança de Admin
    if session.get('nivel_acesso') not in ['admin', 'superadmin']:
        return redirect('/')

    if request.method == 'POST':
        nome = request.form.get('nome_completo')
        email = request.form.get('email').strip().lower()
        tipo = request.form.get('tipo_ingresso')

        conn = psycopg2.connect(URL_BANCO)
        cursor = conn.cursor()
        
        try:
            # 1. O Radar: Puxa o ID e o Nome que já está no banco
            cursor.execute('SELECT id, nome_completo FROM usuarios WHERE email = %s', (email,))
            usuario_existente = cursor.fetchone()

            if usuario_existente:
                usuario_id = usuario_existente[0]
                nome_banco = usuario_existente[1] # O nome verdadeiro do dono do e-mail
                
                # Atualiza o nome só se o banco estava vazio
                if not nome_banco or str(nome_banco).strip() == "":
                    cursor.execute('UPDATE usuarios SET nome_completo = %s WHERE id = %s', (nome, usuario_id))
                    nome_banco = nome

                ingressos_reais = []
                if tipo == 'aula_1': ingressos_reais = ['aula_1', 'espectador']
                elif tipo == 'aula_2': ingressos_reais = ['aula_2', 'espectador']
                elif tipo == 'pacote_aulas': ingressos_reais = ['aula_1', 'aula_2', 'espectador']
                elif tipo == 'competidor': ingressos_reais = ['batalhas', 'espectador']
                else: ingressos_reais = ['espectador']

                # Dá os ingressos separados (com check-in FALSE porque a pessoa ainda não chegou)
                for ing in ingressos_reais:
                    # O Radar: Olha no banco se já existe esse exato ingresso para esse usuário
                    cursor.execute('SELECT id FROM ingressos WHERE usuario_id = %s AND tipo_ingresso = %s', (usuario_id, ing))
                    ingresso_ja_existe = cursor.fetchone()
                    
                    # Se não existir, aí sim ele insere no banco
                    if not ingresso_ja_existe:
                        cursor.execute('INSERT INTO ingressos (usuario_id, tipo_ingresso, checkin_realizado) VALUES (%s, %s, FALSE)', (usuario_id, ing))
                
                conn.commit()
                
                # MENSAGEM NOVA: Avisa na cara de quem ficou o ingresso!
                msg = f"✅ Ingresso adicionado! (Nota: O e-mail usado já pertencia a {nome_banco}, então o ingresso foi para a conta dele)."
                
            else:
                # ... resto do código continua igual (criação de conta nova) ...
                # A pessoa não tem conta. Vamos criar uma com senha padrão.
                senha_padrao = "nextmove2026"
                cursor.execute('''
                    INSERT INTO usuarios (nome_completo, email, senha, nivel_acesso) 
                    VALUES (%s, %s, %s, 'comum') RETURNING id
                ''', (nome, email, senha_padrao))
                novo_usuario_id = cursor.fetchone()[0]
                
                # E agora damos o ingresso
                cursor.execute('INSERT INTO ingressos (usuario_id, tipo_ingresso, checkin_realizado) VALUES (%s, %s, FALSE)', (novo_usuario_id, tipo))
                msg = f"✅ Conta criada e ingresso adicionado! Avise {nome} que a senha de acesso é: {senha_padrao}"
            
            conn.commit()
            return render_template('portaria/venda_antecipada.html', mensagem_sucesso=msg)

        except Exception as e:
            conn.rollback()
            return render_template('portaria/venda_antecipada.html', erro=str(e))
        finally:
            conn.close()

    return render_template('portaria/venda_antecipada.html')