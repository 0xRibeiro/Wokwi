import network, urequests, time, ntptime, dht, json, umail
from machine import Pin
from umqtt.simple import MQTTClient

# Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("Wokwi-GUEST", "")


while not wlan.isconnected():
    time.sleep(0.5)

ntptime.settime()

# Variaveis

soma_temperatura = 0
soma_umidade = 0
quantidade = 0

# Email
sender_email = '0camusproject@gmail.com'
sender_name = 'Victor'
sender_app_password = 'senha do email aqui'
recipient_email ='test@g.br'
email_subject ='Envio do Relatorio'


# Sensor
sensor = dht.DHT22(Pin(23))

# Google Sheets
URL = "https://script.google.com/macros/s/AKfycbxtvvP886atKprkH8UXFII8cpXSgJ5sIKflcz--FDZvLgBYsNrzbjU7OHvkdkBxUq39/exec"

# MQTT
BROKER = "42147c07a9cf4d4a94807a58b97ccaae.s1.eu.hivemq.cloud"

mqtt = MQTTClient(
    b"esp32_estacao1",
    BROKER,
    user="Victor_S",
    password="Teste123",
    port=8883,
    ssl=True,
    ssl_params={"server_hostname": BROKER}
)

try:
    mqtt.connect()
except:
    mqtt = None

# Controle diário
inicio_dia = time.time()

while True:
    try:
        data = time.localtime()

        # Formatando a hora que o localitme retorna para melhor visualização.
        data_formatada = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format( 
            data[0],
            data[1],
            data[2],
            data[3],
            data[4],
            data[5]
            )

        # Leitura
        sensor.measure()

        temperatura = sensor.temperature()
        umidade = sensor.humidity()
        data = time.localtime()

        # Soma médias
        soma_temperatura += temperatura
        soma_umidade += umidade
        quantidade += 1

        # Dados normais
        leitura = {
            "temperatura": temperatura,
            "umidade": umidade,
            "data": data_formatada
        }

        # Envia leitura
        r = urequests.post(URL, json=leitura)
        r.close()

        # Publica MQTT
        if mqtt:
            mqtt.publish(b"estacao/clima", json.dumps(leitura))

        print("Temp:", temperatura, "°C | Umid:", umidade, "%", "Data:", data_formatada)

        # Relatório diário
        if time.time() - inicio_dia >= 60:

            media_temperatura = round(soma_temperatura / quantidade, 2)
            media_umidade = round(soma_umidade / quantidade, 2)

            relatorio = {
                "data_referencia": data_formatada,
                "media_temperatura": media_temperatura,
                "media_umidade": media_umidade,
                "quantidade_leituras": quantidade
            }

            # Envia relatório
            r = urequests.post(URL, json=relatorio)
            r.close()

            # Publica relatório
            if mqtt:
                mqtt.publish(
                    b"estacao/relatorio",
                    json.dumps(relatorio)
                )

            print("\nRELATÓRIO DIÁRIO")
            print(relatorio)

            # Email envio

            data_referencia = relatorio["data_referencia"]
            media_temperatura = relatorio["media_temperatura"]
            media_umidade = relatorio["media_umidade"]
            quantidade_leituras = relatorio["quantidade_leituras"]

            smtp = umail.SMTP('smtp.gmail.com', 465, ssl=True)

            smtp.login(sender_email, sender_app_password)
            smtp.to(recipient_email)

            mensagem = f"""From: {sender_email}

            Nome: Jose Victor Ribeiro da Silva
            RGM: 11231103951 

            Relatorio Diario

            Data referencia: {data_referencia}
            Media temperatura: {media_temperatura} C
            Media umidade: {media_umidade} %
            Quantidade leituras: {quantidade_leituras}
            """

            smtp.send(mensagem)
            smtp.quit()

            # Reinicia contadores
            soma_temperatura = 0
            soma_umidade = 0
            quantidade = 0
            inicio_dia = time.time()


        # Leitura a cada 5s
        time.sleep(5)

    except Exception as e:

        print("Erro:", e)

        try:
            mqtt.connect()
        except:
            pass

        time.sleep(5)
