#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import time
import socket
import threading
import json
from pathlib import Path
try:
    from .env_loader import load_required_env, parse_int_env
    from .csv_writter import load_csv, save_csv
    from .logger_setup import setup_logger
except ImportError:
    from env_loader import load_required_env, parse_int_env
    from csv_writter import load_csv, save_csv
    from logger_setup import setup_logger

logger = setup_logger(__name__)

LOOP_INTERVAL = 5


def load_config():
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        env_file = Path.cwd() / "server" / "src" / ".env"
    env = load_required_env(env_file, ["SERVER_IP", "PORT_NUMBER"], logger)
    return env["SERVER_IP"], parse_int_env(env["PORT_NUMBER"], "PORT_NUMBER", logger)

def status_check(dht_temp, dht_humid, status):
    if dht_temp is None or dht_humid is None or not status:
        logger.warning("Missing fields in sensor data")
        return "ERROR"
    if dht_humid < 0 or dht_humid > 100:
        status = "ERROR"
        logger.warning("Humidity out of range (0-100), setting status to ERROR")
    elif dht_temp < -10 or dht_temp > 60:
        status = "WARNING"
        logger.warning("Temperature out of range (-10 to 60), setting status to WARNING")
    elif dht_humid < 10 or dht_humid > 95:
        status = "WARNING"
        logger.warning("Humidity out of range (10-95), setting status to WARNING")
    else:
        status = "OK"
        logger.info("Sensor data is within normal range, setting status to OK")

    return status

def parse_sensor_payload(data_r_json):
    data_r_list = json.loads(data_r_json)
    data0 = data_r_list[0]
    timestamp = data0["timestamp"]
    raspi_id = data0["raspi_id"]
    sensor_id = data0["sensor_id"]
    dht_temp = data0["tempe_dht_1"]
    dht_humid = data0["humid_dht_1"]
    status = data0["status"]
    checked_status = status_check(dht_temp, dht_humid, status)
    return [timestamp, raspi_id, dht_temp, dht_humid, sensor_id, checked_status]

def save_sensor_payload(data_r_json):
    row = parse_sensor_payload(data_r_json)
    load_csv()
    save_csv([row])
    return row

"""
def save_json(data_r_json):
"""

def server(server_v1, waiting_port_v1):

    stop_event = threading.Event()

    def recv_data1024(socket1, client_address1):
        try:
            logger.info("Start receiving data client=%s", client_address1)
            data_r = socket1.recv(1024)
            if not data_r:
                logger.warning("Received empty data client=%s", client_address1)
                return

            data_r_json = data_r.decode('utf-8')
            logger.info("Received JSON client=%s bytes=%s payload=%s", client_address1, len(data_r), data_r_json)

            save_sensor_payload(data_r_json)

            time.sleep(LOOP_INTERVAL)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            logger.exception("Invalid sensor payload client=%s raw=%r", client_address1, data_r if 'data_r' in locals() else None)
        except OSError:
            logger.exception("Socket or file error while handling client=%s", client_address1)
        except Exception:
            logger.exception("Unexpected error while handling client=%s", client_address1)
        finally:
            logger.info("Closing data socket client=%s", client_address1)
            socket1.close()


    # socoket for waiting of the requests.
    # AF_INET     : IPv4
    # SOCK_STREAM : TCP
    socket_w = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    socket_w.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    node_s = server_v1
    port_s = waiting_port_v1
    logger.info("Binding server socket host=%s port=%s", node_s, port_s)
    socket_w.bind((node_s, port_s))

    BACKLOG = 5
    socket_w.listen(BACKLOG)

    logger.info("Waiting for client connections host=%s port=%s", node_s, port_s)

    def accept_connections():
        while not stop_event.is_set():
            try:
                socket_w.settimeout(1)
                socket_s_r, client_address = socket_w.accept()
                logger.info("Connection established client=%s", client_address)

                thread = threading.Thread(target=recv_data1024,
                    args=(socket_s_r, client_address),
                    daemon=True)
                thread.start()
            except socket.timeout:
                continue
            except OSError:
                if stop_event.is_set():
                    break
                logger.exception("Accept failed")

    accept_thread = threading.Thread(target=accept_connections)
    accept_thread.start()
    logger.info("Started accept thread name=%s", accept_thread.name)

    try:
        while not stop_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Ctrl-C is hit!")
        stop_event.set()
        accept_thread.join()
        logger.info("Closing waiting socket")
        socket_w.close()



def main():
    server_host, server_port = load_config()

    sys_argc = len(sys.argv)
    count = 1
    hostname_v = server_host
    waiting_port_v = server_port

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

            count = count + 1
    logger.info("Start sensor_receiver.py host=%s port=%s", hostname_v, waiting_port_v)

    server(hostname_v, waiting_port_v)


if __name__ == '__main__':
    main()
