let indiceAtual = 0;

function atualizarCarrossel() {
    if (totalBatalhasInicial === 0) return;

    // Esconde todos
    document.querySelectorAll('.card-batalha').forEach(card => card.classList.remove('ativa'));
    
    // Mostra só o atual
    const cardAtual = document.getElementById(`card-${indiceAtual}`);
    if (cardAtual) cardAtual.classList.add('ativa');

    // Atualiza botões e texto
    document.getElementById('btn-ant').disabled = (indiceAtual === 0);
    document.getElementById('btn-prox').disabled = (indiceAtual === totalBatalhasInicial - 1);
    document.getElementById('contador-batalhas').innerText = `${indiceAtual + 1} / ${totalBatalhasInicial}`;
}

function mudarBatalha(direcao) {
    indiceAtual += direcao;
    if (indiceAtual < 0) indiceAtual = 0;
    if (indiceAtual >= totalBatalhasInicial) indiceAtual = totalBatalhasInicial - 1;
    atualizarCarrossel();
}

function fazerPalpite(batalhaId, competidorId) {
    const msgDiv = document.getElementById(`msg-${batalhaId}`);
    msgDiv.innerText = "Salvando palpite...";
    msgDiv.style.color = "#888";

    fetch(`/enviar_palpite/${batalhaId}/${competidorId}`, { method: 'POST' })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'sucesso') {
            document.querySelectorAll(`#card-${indiceAtual} .btn-voto`).forEach(btn => {
                btn.classList.remove('selecionado');
            });

            document.getElementById(`btn-${batalhaId}-${competidorId}`).classList.add('selecionado');
            msgDiv.innerText = "Palpite salvo! ✓";
            msgDiv.style.color = "#00ff41";
        } else {
            msgDiv.innerText = data.mensagem;
            msgDiv.style.color = "#e63946";
        }
    })
    .catch(error => {
        msgDiv.innerText = "Erro ao conectar.";
        msgDiv.style.color = "#e63946";
    });
    document.querySelectorAll('.card-batalha').forEach(card => card.classList.remove('ativa'));
}

// 📡 O RADAR DE TEMPO REAL
function checarNovaRodada() {
    fetch('/verificar_atualizacoes')
    .then(response => response.json())
    .then(data => {
        // Se a quantidade de batalhas no banco for maior do que as que eu tenho na tela...
        if (data.total_batalhas > totalBatalhasInicial) {
            // ...MOSTRA O BOTÃO VERDE FLUTUANTE!
            document.getElementById('btn-nova-rodada').style.display = 'block';
        }
    })
    .catch(err => console.error("Erro no radar:", err));
}

// Quando a página carrega:
window.onload = () => {
    atualizarCarrossel();
    
    // Liga o radar para rodar a cada 5 segundos (5000 milissegundos)
    setInterval(checarNovaRodada, 5000);
};
window.onload = () => {
    
    // 1. O JS escaneia os cards para achar a primeira batalha sem voto
    for (let i = 0; i < totalBatalhasInicial; i++) {
        let card = document.getElementById(`card-${i}`);
        if (card) {
            let jaVotou = card.querySelector('.selecionado') !== null;
            let finalizada = card.querySelector('button:disabled') !== null;

            // Se ainda não votou e a batalha não acabou, essa é a nossa parada!
            if (!jaVotou && !finalizada) {
                indiceAtual = i;
                break; // Achou! Pode parar de procurar.
            }
        }
    }

    // 2. Monta o carrossel no índice que ele acabou de descobrir
    atualizarCarrossel();
    
    // 3. Liga o radar de tempo real para rodar a cada 5 segundos
    setInterval(checarNovaRodada, 20000);
};