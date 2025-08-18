from .data_server import DataSaver, BaseDataServer
import paho.mqtt.client as mqtt

class MQTTlogBridge:
    def __init__(self, raw_feed, mqtt_host, auth={}):
        self.saver = DataSaver()
        self.thread = self.saver.make_thread()
        self.thread.start()

        self.raw_feed = raw_feed

        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.on_connect = self.on_connect
        mqttc.on_message = self.on_message

        if 'username' in auth:
            mqttc.username = auth['username']
        if 'password' in auth:
            mqttc.password = auth['password']

        mqttc.connect(mqtt_host, 1883, 60)
        mqttc.loop_start()
        self.mqttc = mqttc

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}")
        client.subscribe(self.raw_feed)

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        feed_header = self.raw_feed.replace("#", '')
        key = msg.topic.replace(feed_header, "").encode()
        with BaseDataServer.save_lock:
            to_log = []
            if key in BaseDataServer.pending_save:
                to_log = BaseDataServer.pending_save[key]
            else:
                BaseDataServer.pending_save[key] = to_log
            to_log.append(msg.payload)
    
    def stop(self):
        self.mqttc.loop_stop()
        self.saver._running_ = False
        self.thread.join()

if __name__ == "__main__":
    '''
    usage: py <mqtt address> <raw data feed> [username] [password]
    '''
    import sys
    host = sys.argv[1]
    feed = sys.argv[2]
    auth = {
        'username': sys.argv[3],
        'password': sys.argv[4],
    }
    handler = MQTTlogBridge(feed, host, auth)
    input()
    handler.stop()