import json
import time
import logging
import paho.mqtt.client as mqtt
import threading


class MqttHandler:
    def __init__(self, host, port, username, password):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connected = False
        self.client.tls_set(
              ca_certs="/root/grekhov/speechmate-tech-certs/speechmate_tech_ca.crt",
              certfile="/root/grekhov/speechmate-tech-certs/speechmate_tech_client.crt",
              keyfile="/root/grekhov/speechmate-tech-certs/speechmate_tech_client.key")

        try:
            self.client.connect(host, port, 60)
            self.client.loop_start()
        except Exception as e:
            logging.error(f"Connection error: {e}")

        self.response_event = threading.Event()
        self.response_data = None

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        logging.info(f"Подключено к MQTT с кодом результата: {reason_code}")
        self.client.subscribe("$SYS/#")
        self.connected = True

    def on_message(self, client, userdata, message):
        payload = message.payload.decode()

        try:
            response = json.loads(payload)
            if 'cmd' in response:
                self.response_data = response
                self.response_event.set()
        except json.JSONDecodeError:
            logging.error("Received non-JSON message")

    def wait_for_response(self, timeout=30):
        self.response_event.clear()
        self.response_event.wait(timeout)
        return self.response_data

    def publish_command(self, hub_id, command):
        try:
            if not self.connected:
                logging.error("MQTT client is not connected. Cannot publish command.")
                return
            topic = f"{hub_id}/cmd"
            payload = {
                "cmd": command,
                "ts": int(time.time())
            }
            self.client.publish(topic, json.dumps(payload))
            logging.info(f"Published to {topic}: {payload}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
        logging.info("Отключаюсь от MQTT.")
