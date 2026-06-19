import sys
import time
import socket
import threading
import json
import csv

SERVER = "localhost"
WAITING_PORT = 8765
CSV_FILE = "sensor_readings.csv"

LOOP_INTERVAL = 5

def load_csv(filepath):
    try:
        with open(filepath) as f:
            all_data_iter = csv.reader(f)
            for row in all_data_iter:
                print(row)
    except FileNotFoundError:
        print(f"{filepath} が見つかりません。新規作成します。")
        with open(filepath, mode='w') as f:
            write_iter = csv.writer(f)
            write_iter.writerow(["tempe_dht_1", "humid_dht_1"])


def save_csv(filepath, data):
    with open(filepath, mode='a') as f:
        write_iter = csv.writer(f)
        for row in data:
            write_iter.writerow(row)
    print(f" {filepath} に保存しました。")

def server(server_v1=SERVER, waiting_port_v1=WAITING_PORT):

    stop_event = threading.Event()

    def recv_data1024(socket1, client_address1):
        data_r = socket1.recv(1024)
        data_r_json = data_r.decode('utf-8')
        data_r_list = json.loads(data_r_json)

        data0 = data_r_list[0]
        dht_temp = data0["tempe_dht_1"]
        dht_humid = data0["humid_dht_1"]

        load_csv(CSV_FILE)
        save_csv(CSV_FILE, [[dht_temp, dht_humid]])


        time.sleep(LOOP_INTERVAL)

        print("Now, closing the data socket.")
        socket1.close()


    # socoket for waiting of the requests.
    # AF_INET     : IPv4
    # SOCK_STREAM : TCP
    socket_w = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    socket_w.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    node_s = server_v1
    port_s = waiting_port_v1
    socket_w.bind((node_s, port_s))

    BACKLOG = 5
    socket_w.listen(BACKLOG)

    print('Waiting for the connection from the client(s). '
        + 'node: ' + node_s + '  '
        + 'port: ' + str(port_s))

    def accept_connections():
        while not stop_event.is_set():
            try:
                socket_w.settimeout(1)
                socket_s_r, client_address = socket_w.accept()
                print('Connection from '
                    + str(client_address)
                    + " has been established.")

                thread = threading.Thread(target=recv_data1024,
                    args=(socket_s_r, client_address),
                    daemon=True)
                thread.start()
            except socket.timeout:
                continue

    accept_thread = threading.Thread(target=accept_connections)
    accept_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        print("Ctrl-C is hit!")
        stop_event.set()
        accept_thread.join()
        print("Now, closing the waiting socket.")
        socket_w.close()



if __name__ == '__main__':

    sys_argc = len(sys.argv)
    count = 1
    hostname_v = SERVER
    waiting_port_v = WAITING_PORT

    while True:
            print(count, "/", sys_argc)
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
    print(hostname_v)
    print(waiting_port_v)

    server(hostname_v, waiting_port_v)
