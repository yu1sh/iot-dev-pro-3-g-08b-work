# IoTデバイスプログラミング３（2026）G-08B

## ファイル階層

```text
.
├── README.md
├── pyproject.toml
├── Android/                   # Android端末用
│   └── index.html
├── client/                    # センサー接続端末用
│   ├── logs/                  # 実行時に作成
│   │   └── sensor_client_YYYYMMDD-HHMMSS.log
│   ├── outputs/               # 実行時に作成
│   │   └── failed_sensor_readings.csv
│   └── src/
│       ├── .env.example
│       ├── csv_writter.py
│       ├── dht22_takemoto.py
│       ├── logger_setup.py
│       └── sensor_client.py
├── server/                    # サーバー端末用
│   ├── logs/                  # 実行時に作成
│   │   └── sensor_server_YYYYMMDD-HHMMSS.log
│   ├── outputs/               # 実行時に作成
│   │   └── sensor_readings.csv
│   └── src/
│       ├── csv_writter.py
│       ├── logger_setup.py
│       ├── sensor_receiver.py
│       ├── web_dashboard.py
│       └── templates/
│           └── dashboard.html
└── systemd/
    └── iot-sensor_client.service
```

- `client/`: センサーを接続した端末で使用するクライアント側プログラム
- `server/`: センサーデータを受信・記録・Web表示するサーバー端末用プログラム
- `Android/`: Android端末で表示するHTMLファイル
- `client/src/`: クライアント側のソースコード
- `server/src/`: サーバー側のソースコード
- `server/src/templates/`: Webダッシュボード用のHTMLテンプレート
- `client/logs/`: クライアント実行時に作成されるログ保存先
- `client/outputs/`: サーバー送信に失敗したセンサーデータのCSV保存先
- `server/logs/`: サーバー実行時に作成されるログ保存先
- `server/outputs/`: 受信したセンサーデータのCSV保存先
- `systemd/`: Raspberry Pi起動時にクライアントを自動実行するserviceファイル

## プログラムの流れ

このシステムは、センサーを接続したRaspberry Pi側のクライアントと、データを受信するサーバー側のプログラムで動作します。

1. Raspberry Pi側で `client/src/sensor_client.py` を起動します。
2. クライアントはDHT22センサーから温度と湿度を読み取ります。
3. 読み取った値に、時刻・Raspberry Pi ID・センサーID・状態を付けてJSON形式のデータを作成します。
4. 作成したデータをTCP通信でサーバー側の `server/src/sensor_receiver.py` に送信します。
5. サーバーは受信したデータを確認し、温度や湿度の値に応じて `OK`、`WARNING`、`ERROR` の状態を判定します。
6. 判定後のデータは `server/outputs/sensor_readings.csv` に保存されます。
7. `server/src/web_dashboard.py` を起動すると、保存されたCSVデータをWebブラウザから確認できます。

DHT22センサーの読み取りに失敗した場合、クライアントはその回の送信を行わず、温度・湿度を空欄、状態を `ERROR` として `client/outputs/failed_sensor_readings.csv` に保存します。

サーバーへ送信できなかった場合も、クライアント側で状態を `SEND_FAILED` として同じCSVに保存します。

## Raspberry Piでの自動起動設定

`systemd/iot-sensor_client.service` は、Raspberry Pi起動時に `client/src/sensor_client.py` を自動実行するためのserviceファイルです。

前提:

- Raspberry Pi上のリポジトリ配置先: `/home/raspi4/iot-dev-pro-3-g-08b-work`
- 仮想環境: `/home/raspi4/iot-dev-pro-3-g-08b-work/venv`
- 実行ユーザー: `raspi4`
- 設定ファイル: `client/src/.env`

`client/src/.env` は `client/src/.env.example` を参考に作成します。

```env
SERVER_IP = "10.192.139.5"
PORT_NUMBER = 8765
```

serviceを登録して起動する手順:

```bash
sudo cp systemd/iot-sensor_client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable iot-sensor_client.service
sudo systemctl start iot-sensor_client.service
```

状態確認:

```bash
systemctl status iot-sensor_client.service
journalctl -u iot-sensor_client.service -f
```

serviceを変更した場合は、再読み込みして再起動します。

```bash
sudo systemctl daemon-reload
sudo systemctl restart iot-sensor_client.service
```

PC側では、Raspberry Piからの送信を受けるために `server/src/sensor_receiver.py` を起動しておきます。
