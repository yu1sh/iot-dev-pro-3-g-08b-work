import sys
import time
import socket
import threading
import json
from csv_storage import CSV_FILE, load_csv, save_csv
from logger_setup import setup_logger

logger = setup_logger(__name__)

SERVER = "localhost"
WAITING_PORT = 8765

LOOP_INTERVAL = 5

def server(server_v1=SERVER, waiting_port_v1=WAITING_PORT):

    stop_event = threading.Event()

    def recv_data1024(socket1, client_address1):
        try:
            logger.info("Start receiving data client=%s", client_address1)
            data_r = socket1.recv(1024)
            if not data_r:
                logger.warning("Received empty data client=%s", client_address1)
                return

            data_r_json = data_r.decode('utf-8')
            data_r_list = json.loads(data_r_json)
            logger.info("Received JSON client=%s bytes=%s payload=%s", client_address1, len(data_r), data_r_json)

            data0 = data_r_list[0]
            raspi_id = data0["raspi_id"]
            dht_temp = data0["tempe_dht_1"]
            dht_humid = data0["humid_dht_1"]
            timestamp = data0["timestamp"]

            load_csv(CSV_FILE)
            save_csv(CSV_FILE, [[raspi_id, dht_temp, dht_humid, timestamp]])

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



if __name__ == '__main__':

    sys_argc = len(sys.argv)
    count = 1
    hostname_v = SERVER
    waiting_port_v = WAITING_PORT

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
