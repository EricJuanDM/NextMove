from locust import HttpUser, task, between

class Espectador(HttpUser):
    # Simula o tempo que uma pessoa real leva lendo a tela antes de clicar em algo (entre 5 e 20 segundos)
    wait_time = between(5, 20)

    @task(3)
    def carregar_tela_votacao(self):
        # O robô acessa a tela principal do bolão (peso 3: ele faz isso com mais frequência)
        self.client.get("/votacao")

    @task(1)
    def checar_radar(self):
        # O robô simula aquele JavaScript que verifica se tem rodada nova (peso 1)
        self.client.get("/verificar_atualizacoes")