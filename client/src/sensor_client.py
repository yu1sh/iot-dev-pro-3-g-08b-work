#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import json
import dht22_takemoto as dht22
import time
from datetime import datetime
from logger_setup import setup_logger
from csv_writter import load_csv, save_csv

logger = setup_logger(__name__)

RASPI_ID = "raspi_001"
SENSOR_ID = "dht_1"
STATUS = "OK"

SERVER = 'localhost'
WAITING_PORT = 8765
MESSAGE_FROM_CLIENT = "This is a client test message."

MAX_SEND_RETRY = 3
WAIT_INTERVAL = 10
WAIT_INTERVAL_RETRY = 5
SOCKET_TIMEOUT = 10

dht22_instance = dht22.DHT22(gpio=26)

def save_local_csv(timestamp, tempe, humid, current_status):
    load_csv()
    save_csv([[timestamp, RASPI_ID, tempe, humid, SENSOR_ID, current_status]])


def build_sensor_payload(timestamp, tempe, humid, current_status=STATUS):
    return [{
            "timestamp": timestamp,
            "raspi_id": RASPI_ID,
            "sensor_id": SENSOR_ID,
            "tempe_dht_1": tempe,
            "humid_dht_1": humid,
            "status": current_status
            }]


def get_dht_data():
    tempe = 200.0 # unnecessary value-setting
    hum = 100.0 # unnecessary value-setting

    try:
        tempe, hum, check = dht22_instance.read()
        logger.info("DHT22 read success temperature=%.1f humidity=%.1f", tempe, hum)

    except dht22.DHT22CRCError:
        logger.warning("DHT22CRCError while reading sensor")
        time.sleep(WAIT_INTERVAL_RETRY)
        return None

    except dht22.DHT22MissingDataError:
        logger.warning("DHT22MissingDataError while reading sensor")
        time.sleep(WAIT_INTERVAL_RETRY)
        return None

    except Exception:
        logger.exception("Unexpected error while reading DHT22")
        time.sleep(WAIT_INTERVAL_RETRY)
        return None

    return float(tempe), float(hum)


def client_test(hostname_v1 = SERVER, waiting_port_v1 = WAITING_PORT, message1 = MESSAGE_FROM_CLIENT):
    import socket
    import time

    node_s = hostname_v1
    port_s = waiting_port_v1

    try:
        while True:
            dht_data = get_dht_data()
            if dht_data is None:
                logger.warning("Failed to get DHT22 data, skipping this iteration")
                save_local_csv(datetime.now().strftime('%Y%m%d-%H%M%S'), None, None, "ERROR")
                continue

            tempe, humid = dht_data
            current_status = STATUS
            data_s_list = build_sensor_payload(
                datetime.now().strftime('%Y%m%d-%H%M%S'),
                tempe,
                humid,
                current_status,
            )
            data_s_json = json.dumps(data_s_list)
            data_s = data_s_json.encode('utf-8')

            # socoket for receiving and sending data
            # AF_INET     : IPv4
            # SOCK_STREAM : TCP
            for retry_count in range(MAX_SEND_RETRY+1):
                socket_r_s = None
                try:
                    socket_r_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    socket_r_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    socket_r_s.settimeout(SOCKET_TIMEOUT)
                    logger.info("Connecting to server host=%s port=%s", node_s, port_s)
                    socket_r_s.connect((node_s, port_s))
                    logger.info("Connected to server host=%s port=%s", node_s, port_s)

                    socket_r_s.sendall(data_s)
                    logger.info("Sent sensor data host=%s bytes=%s payload=%s", node_s, len(data_s), data_s_json)
                    break  # 正常に送信できたため、ループを抜ける
                except (socket.timeout, ConnectionError, OSError):
                    logger.exception("Failed to send sensor data host=%s port=%s", node_s, port_s)

                    if retry_count < MAX_SEND_RETRY:
                        logger.info("Retrying to send data host=%s port=%s retry_count=%s", node_s, port_s, retry_count + 1)
                        time.sleep(WAIT_INTERVAL_RETRY)
                    else:
                        logger.error("Max send retry reached host=%s port=%s", node_s, port_s)
                        current_status = "SEND_FAILED"
                        data_s_list[0]["status"] = current_status
                        save_local_csv(data_s_list[0]["timestamp"], tempe, humid, current_status)
                        logger.info("Failed data saved locally payload=%s", json.dumps(data_s_list))
                        break  # 最大リトライ回数に達したため、ループを抜ける

                finally:
                    if socket_r_s is not None:
                        socket_r_s.close()
                        logger.info("Closed client socket host=%s port=%s", node_s, port_s)

            time.sleep(WAIT_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Ctrl-C is hit!")
        logger.info("End of this client.")
    except Exception:
        logger.exception("Unexpected client error")


if __name__ == '__main__':
    logger.info("Start sensor_client.py")

    sys_argc = len(sys.argv)
    count = 1
    hostname_v = SERVER
    waiting_port_v = WAITING_PORT
    message_v = MESSAGE_FROM_CLIENT

    while True:
        if(count >= sys_argc):
            break

        option_key = sys.argv[count]
        if ("-h" == option_key):
            count = count + 1
            hostname_v = sys.argv[count]
        if ("-p" == option_key):
            count = count + 1
            waiting_port_v = int(sys.argv[count])
        if ("-m" == option_key):
            count = count + 1
            message_v = sys.argv[count]

        count = count + 1

    logger.info(
        "Client settings host=%s port=%s message=%s",
        hostname_v,
        waiting_port_v,
        message_v,
    )

    client_test(hostname_v, waiting_port_v, message_v)
