#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

# Sample Implemantation of IPUT Course IoT Device Programming 3 (2022 Summer)
# Michiharu Takemoto (takemoto.development@gmail.com)
#
# 2022/05/10
# Socket Client WITH BLANK
#
# NOT MIT License
#

import sys
import json
import dht22_takemoto as dht22
import time
import datetime
import logging
from pathlib import Path

dht22_instance = dht22.DHT22(gpio=26)
raspi_id = "raspi_001"

LOG_DIR = Path(__file__).with_name("logs")
LOG_FILE = LOG_DIR / f"sensor_{datetime.datetime.now().strftime('%Y%m%d')}.log"


def setup_logger():
    LOG_DIR.mkdir(exist_ok=True)

    logger_v = logging.getLogger(__name__)
    logger_v.setLevel(logging.INFO)

    if logger_v.handlers:
        return logger_v

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger_v.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger_v.addHandler(stream_handler)

    return logger_v


logger = setup_logger()

SERVER = 'localhost'
WAITING_PORT = 8765
MESSAGE_FROM_CLIENT = "Hello, I am a client."

MAX_SEND_RETRY = 3
WAIT_INTERVAL = 5
WAIT_INTERVAL_RETRY = 5
SOCKET_TIMEOUT = 10

def get_dht_data():
    tempe = 200.0 # unnecessary value-setting
    hum = 100.0 # unnecessary value-setting

    try:
        tempe, hum, check = dht22_instance.read()
        print('Last valid input: ' + str(datetime.datetime.now()))
        print('Temperature: %-3.1f C' % tempe)
        print('Humidity: %-3.1f %%' % hum)
        logger.info("DHT22 read success temperature=%.1f humidity=%.1f", tempe, hum)

    except dht22.DHT22CRCError:
        print('DHT22CRCError: ' + str(datetime.datetime.now()))
        logger.warning("DHT22CRCError")
        time.sleep(WAIT_INTERVAL_RETRY)
        return None

    except dht22.DHT22MissingDataError:
        print('DHT22MissingDataError: ' + str(datetime.datetime.now()))
        logger.warning("DHT22MissingDataError")
        time.sleep(WAIT_INTERVAL_RETRY)
        return None

    return float(tempe), float(hum)


def client_test(hostname_v1 = SERVER, waiting_port_v1 = WAITING_PORT, message1 = MESSAGE_FROM_CLIENT):
    import socket
    import time

    node_s = hostname_v1
    port_s = waiting_port_v1

    try:
        count = 0
        while True:
            dht_data = get_dht_data()
            if dht_data is None:
                continue

            tempe, humid = dht_data

            # socoket for receiving and sending data
            # AF_INET     : IPv4
            # SOCK_STREAM : TCP
            socket_r_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_r_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socket_r_s.settimeout(SOCKET_TIMEOUT)
            print("node_s:", node_s,  " port_s:", str(port_s))
            socket_r_s.connect((node_s, port_s))
            print('Connecting to the server. '
                + 'node: ' + node_s + '  '
                + 'port: ' + str(port_s))
            logger.info("Connected to server host=%s port=%s", node_s, port_s)

            data_s_list = [{"raspi_id": raspi_id, "tempe_dht_1": tempe, "humid_dht_1": humid, "timestamp": str(datetime.datetime.now())}]
            data_s_json = json.dumps(data_s_list)
            # data_s = bytes(data_s_str, encoding = 'utf-8')
            data_s = data_s_json.encode('utf-8')
            socket_r_s.send(data_s)
            print('I (a client) have just sent data __'
                + data_s_json
                + '__ to the server ' + node_s + ' .')
            logger.info("Sent sensor data host=%s payload=%s", node_s, data_s_json)

            socket_r_s.close()

            time.sleep(WAIT_INTERVAL)

            count = count + 1
            if count > MAX_SEND_RETRY:
                break

    except KeyboardInterrupt:
        logger.info("Ctrl-C is hit!")
        logger.info("End of this client.")



if __name__ == '__main__':
    print("Start if __name__ == '__main__'")
    logger.info("Start sensor_client.py")

    sys_argc = len(sys.argv)
    count = 1
    hostname_v = SERVER
    waiting_port_v = WAITING_PORT
    message_v = MESSAGE_FROM_CLIENT

    while True:
        print(count, "/", sys_argc)
        if(count >= sys_argc):
            break

        option_key = sys.argv[count]
        #print(option_key)
        if ("-h" == option_key):
            count = count + 1
            hostname_v = sys.argv[count]
            #print(option_key, hostname_v)
        if ("-p" == option_key):
            count = count + 1
            waiting_port_v = int(sys.argv[count])
            #print(option_key, port_v)
        if ("-m" == option_key):
            count = count + 1
            message_v = sys.argv[count]
            #print(option_key, message_v)

        count = count + 1

    print(hostname_v)
    print(waiting_port_v)
    print(message_v)
    logger.info(
        "Client settings host=%s port=%s message=%s",
        hostname_v,
        waiting_port_v,
        message_v,
    )

    client_test(hostname_v, waiting_port_v, message_v)
