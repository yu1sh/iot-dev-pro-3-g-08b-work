#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import time
import socket
import threading
import json
import uuid
import hashlib
from collections import OrderedDict
try:
    from .env_loader import find_env_file, load_required_env, parse_int_env
    from .csv_writter import save_csv
    from .logger_setup import setup_logger
except ImportError:
    from env_loader import find_env_file, load_required_env, parse_int_env
    from csv_writter import save_csv
    from logger_setup import setup_logger

logger = setup_logger(__name__)

READ_TIMEOUT = 10
RECV_CHUNK_SIZE = 4096
MAX_PAYLOAD_SIZE = 64 * 1024
MAX_PROCESSED_MESSAGES = 100000
PROCESSED_MESSAGES = OrderedDict()
PROCESSED_MESSAGES_LOCK = threading.Lock()


class PayloadTooLargeError(ValueError):
    pass


class DuplicateMessageConflictError(ValueError):
    pass


def load_config():
    env_file = find_env_file("server")
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

def parse_sensor_message(data_r_json):
    data_r_list = json.loads(data_r_json)
    if not isinstance(data_r_list, list) or len(data_r_list) != 1:
        raise ValueError("Sensor payload must contain exactly one item")
    data0 = data_r_list[0]
    if not isinstance(data0, dict):
        raise TypeError("Sensor payload item must be an object")
    message_id = data0["message_id"]
    if not isinstance(message_id, str) or str(uuid.UUID(message_id)) != message_id:
        raise ValueError("message_id must be a canonical UUID")
    timestamp = data0["timestamp"]
    raspi_id = data0["raspi_id"]
    sensor_id = data0["sensor_id"]
    dht_temp = data0["tempe_dht_1"]
    dht_humid = data0["humid_dht_1"]
    status = data0["status"]
    checked_status = status_check(dht_temp, dht_humid, status)
    row = [
        timestamp,
        raspi_id,
        dht_temp,
        dht_humid,
        sensor_id,
        checked_status,
    ]
    canonical_payload = json.dumps(
        data_r_list,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    fingerprint = hashlib.sha256(canonical_payload).digest()
    return message_id, row, fingerprint


def parse_sensor_payload(data_r_json):
    _, row, _ = parse_sensor_message(data_r_json)
    return row

def save_sensor_payload(data_r_json):
    row = parse_sensor_payload(data_r_json)
    save_csv([row])
    return row


def save_sensor_message_idempotent(message_id, row, fingerprint):
    with PROCESSED_MESSAGES_LOCK:
        existing_fingerprint = PROCESSED_MESSAGES.get(message_id)
        if existing_fingerprint is not None:
            if existing_fingerprint != fingerprint:
                raise DuplicateMessageConflictError(
                    f"message_id already exists with different payload: {message_id}"
                )
            PROCESSED_MESSAGES.move_to_end(message_id)
            return False

        save_csv([row])
        PROCESSED_MESSAGES[message_id] = fingerprint
        if len(PROCESSED_MESSAGES) > MAX_PROCESSED_MESSAGES:
            PROCESSED_MESSAGES.popitem(last=False)
        return True


def encode_response(status, message_id=None, code=None, duplicate=None):
    response = {"status": status}
    if message_id is not None:
        response["message_id"] = message_id
    if code is not None:
        response["code"] = code
    if duplicate is not None:
        response["duplicate"] = duplicate
    return (
        json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )


def send_response(client_socket, status, message_id=None, code=None, duplicate=None):
    client_socket.sendall(
        encode_response(status, message_id, code, duplicate)
    )


def handle_client_connection(client_socket, client_address):
    buffer = bytearray()
    current_message_id = None

    try:
        logger.info("Start receiving data client=%s", client_address)

        while True:
            chunk = client_socket.recv(RECV_CHUNK_SIZE)
            if not chunk:
                if buffer:
                    logger.warning(
                        "Connection closed with incomplete NDJSON client=%s bytes=%s",
                        client_address,
                        len(buffer),
                    )
                return

            buffer.extend(chunk)

            while True:
                newline_index = buffer.find(b"\n")
                if newline_index < 0:
                    if len(buffer) > MAX_PAYLOAD_SIZE:
                        raise PayloadTooLargeError
                    break

                if newline_index > MAX_PAYLOAD_SIZE:
                    raise PayloadTooLargeError

                payload_bytes = bytes(buffer[:newline_index])
                del buffer[:newline_index + 1]

                if not payload_bytes:
                    raise ValueError("Empty NDJSON record")

                payload_json = payload_bytes.decode("utf-8", errors="strict")
                logger.info(
                    "Received JSON client=%s bytes=%s",
                    client_address,
                    len(payload_bytes),
                )

                current_message_id, row, fingerprint = parse_sensor_message(payload_json)
                inserted = save_sensor_message_idempotent(
                    current_message_id,
                    row,
                    fingerprint,
                )
                send_response(
                    client_socket,
                    "ok",
                    current_message_id,
                    duplicate=not inserted,
                )
                logger.info(
                    "Sent ACK client=%s message_id=%s duplicate=%s",
                    client_address,
                    current_message_id,
                    not inserted,
                )
                current_message_id = None

    except PayloadTooLargeError:
        logger.warning(
            "Payload too large client=%s max_bytes=%s",
            client_address,
            MAX_PAYLOAD_SIZE,
        )
        try:
            send_response(client_socket, "error", code="payload_too_large")
        except OSError:
            logger.warning("Could not send error response client=%s", client_address)
    except UnicodeDecodeError:
        logger.exception("Invalid UTF-8 payload client=%s", client_address)
        try:
            send_response(client_socket, "error", code="invalid_utf8")
        except OSError:
            logger.warning("Could not send error response client=%s", client_address)
    except DuplicateMessageConflictError:
        logger.exception(
            "Conflicting duplicate message client=%s message_id=%s",
            client_address,
            current_message_id,
        )
        try:
            send_response(
                client_socket,
                "error",
                current_message_id,
                "message_id_conflict",
            )
        except OSError:
            logger.warning("Could not send error response client=%s", client_address)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        logger.exception("Invalid sensor payload client=%s", client_address)
        try:
            send_response(
                client_socket,
                "error",
                current_message_id,
                "invalid_payload",
            )
        except OSError:
            logger.warning("Could not send error response client=%s", client_address)
    except socket.timeout:
        logger.warning("Read timed out client=%s", client_address)
        try:
            send_response(client_socket, "error", code="timeout")
        except OSError:
            logger.warning("Could not send timeout response client=%s", client_address)
    except OSError:
        logger.exception("Socket or file error while handling client=%s", client_address)
    except Exception:
        logger.exception("Unexpected error while handling client=%s", client_address)
    finally:
        logger.info("Closing data socket client=%s", client_address)
        client_socket.close()

"""
def save_json(data_r_json):
"""

def server(server_v1, waiting_port_v1):

    stop_event = threading.Event()


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
                socket_s_r.settimeout(READ_TIMEOUT)
                logger.info("Connection established client=%s", client_address)

                thread = threading.Thread(target=handle_client_connection,
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
