from machine import Pin, ADC, I2C
import dht
import ssd1306
import time
import network
import json
import ssl
from umqtt.simple import MQTTClient
import urequests as requests



# Sensores do WokWi
dht22 = dht.DHT22(Pin(23))

luz = ADC(Pin(34))
luz.atten(ADC.ATTN_11DB)

qualidade_ar = ADC(Pin(33))
qualidade_ar.atten(ADC.ATTN_11DB)

botao = Pin(17, Pin.IN, Pin.PULL_UP)



# Configura o LED e as variaveis gerais

i2c = I2C(0, scl=Pin(27), sda=Pin(14))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

tela = 2
cliente_mqtt = None
ultimo_envio = 0
INTERVALO_ENVIO = 1

# Conexão WI-FI

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Conectando WiFi...")
        wlan.connect("Wokwi-GUEST", "")

        while not wlan.isconnected():
            pass

    print("WiFi conectado:", wlan.ifconfig())


# Conexão com o HiveMQ
MQTT_BROKER = "42147c07a9cf4d4a94807a58b97ccaae.s1.eu.hivemq.cloud"
MQTT_CLIENT_ID = b"esp32_estacao1"
TOPICO = b"estacao/dados"

def conectar_mqtt():
    global cliente_mqtt
    try:
        cliente_mqtt = MQTTClient(
            MQTT_CLIENT_ID,
            MQTT_BROKER,
            user="Victor",
            password="Tsukuyom1",
            port=8883,
            ssl=True,
            ssl_params={"server_hostname": MQTT_BROKER}
        )
        cliente_mqtt.connect()
        print("MQTT conectado")
    except Exception as e:
        print("Erro MQTT:", e)
        cliente_mqtt = None

# Envia os dados pro HiveMQ
def enviar_dados(temp_wokwi, umid_wokwi, luz_wokwi, ar_wokwi,
                 pressao_api, umidade_api, previsao, cidade):
    global cliente_mqtt

    if cliente_mqtt is None:
        return

    try:
        payload = {
            "temperatura_wokwi": temp_wokwi,
            "umidade_wokwi": umid_wokwi,
            "luminosidade_wokwi": luz_wokwi,
            "qualidade_ar_wokwi": ar_wokwi,
            "pressao_api": pressao_api,
            "umidade_api": umidade_api,
            "previsao": previsao,
            "cidade": cidade
        }

        cliente_mqtt.publish(TOPICO, json.dumps(payload))

    except:
        cliente_mqtt = None


# Leitura do wokwi
def ler():
    try:
        dht22.measure()
        temperatura_wokwi = dht22.temperature()
        umidade_wokwi = dht22.humidity()
    except:
        temperatura_wokwi, umidade_wokwi = 0, 0

    luminosidade_wokwi = luz.read()
    qualidade_wokwi = qualidade_ar.read()

    return temperatura_wokwi, umidade_wokwi, luminosidade_wokwi, qualidade_wokwi

# Calculo e display do conforto termico, seguindo a nomeclatura das fontes.
def indice_conforto(temp, umid):
    return temp - (0.55 - 0.0055 * umid) * (temp - 14.5)

def classificar_conforto(c):
    if c <= 5.9:
        return "Muito frio"
    elif c <= 8.9:
        return "Frio alto"
    elif c <= 11.9:
        return "Frio"
    elif c <= 14.9:
        return "Frio leve"
    elif c <= 17.9:
        return "Pouco frio"
    elif c <= 20.9:
        return "Limite baixo"
    elif c <= 23.9:
        return "Conforto"
    elif c <= 26.9:
        return "Limite alto"
    elif c <= 29.9:
        return "Pouco quente"
    elif c <= 32.9:
        return "Quente"
    else:
        return "Muito quente"



# Lógica do botão pra trocar entre as telas
ultimo_clique = 0
ultimo_estado = 1

def trocar_tela():
    global tela
    global ultimo_clique
    global ultimo_estado

    estado_atual = botao.value()
    agora = time.ticks_ms()

    if ultimo_estado == 1 and estado_atual == 0:

        if time.ticks_diff(agora, ultimo_clique) > 250:

            tela = (tela + 1) % 5
            ultimo_clique = agora

    ultimo_estado = estado_atual


# Dados da API openweathermap
API_KEY = "68237d706cc6ee9f498b22d59c7f570e"
# Cidades Brasileiras não retornaram nada nos meus testes, tive que usar uma de fora.
CIDADE = "London"
URL = "http://api.openweathermap.org/data/2.5/weather?q={}&appid={}&units=metric".format(CIDADE, API_KEY)

def obter_dados_api():
    try:
        r = requests.get(URL)
        data = r.json()

        pressao_api = data["main"]["pressure"]
        temperatura_api = data["main"]["temp"]
        umidade_api = data["main"]["humidity"]

        r.close()

        return pressao_api, temperatura_api, umidade_api

    except:
        return 0, 0, 0


# Calculando uma previsão simplificada
def prever_tempo(pressao_api, temp_api):
    if pressao_api < 1000:
        return "Chuva"
    elif pressao_api < 1015:
        if temp_api > 28:
            return "Abafado"
        return "Nublado"
    else:
        return "Ensolarado"


# Configurando o display das telas do LED

def cidade_curta(nome):
    return nome[:10]

def mostrar(temp_wokwi, umid_wokwi, luz_wokwi, ar_wokwi, pressao_api, previsao):
    oled.fill(0)

    conforto = indice_conforto(temp_wokwi, umid_wokwi)
    texto = classificar_conforto(conforto)

    if tela == 0:
        oled.text("TEMP:", 0, 0)
        oled.text(str(temp_wokwi) + "C", 0, 15)
        oled.text("UMID:" + str(umid_wokwi) + "%", 0, 30)

    elif tela == 1:
        oled.text("LUZ:", 0, 0)
        oled.text(str(luz_wokwi), 0, 20)

    elif tela == 2:
        oled.text("AR:", 0, 0)
        oled.text(str(ar_wokwi), 0, 20)

    elif tela == 3:
        oled.text("CONFORTO", 0, 0)
        oled.text("{:.1f}".format(conforto), 0, 15)
        oled.text(texto[:16], 0, 35)

    elif tela == 4:
        oled.text(cidade_curta(CIDADE), 0, 0)
        oled.text("PRESSAO:", 0, 15)
        oled.text(str(pressao_api), 0, 30)
        oled.text(previsao, 0, 50)

    oled.show()


# Iniciando conexões e ativando o loop

conectar_wifi()
conectar_mqtt()

while True:

    trocar_tela()

    temperatura_wokwi, umidade_wokwi, luminosidade_wokwi, qualidade_wokwi = ler()

    pressao_api, temperatura_api, umidade_api = obter_dados_api()
    previsao = prever_tempo(pressao_api, temperatura_api)

    mostrar(
        temperatura_wokwi,
        umidade_wokwi,
        luminosidade_wokwi,
        qualidade_wokwi,
        pressao_api,
        previsao
    )

    if time.time() - ultimo_envio > INTERVALO_ENVIO:
        enviar_dados(
            temperatura_wokwi,
            umidade_wokwi,
            luminosidade_wokwi,
            qualidade_wokwi,
            pressao_api,
            umidade_api,
            previsao,
            CIDADE
        )
        ultimo_envio = time.time()
    time.sleep_ms(10)