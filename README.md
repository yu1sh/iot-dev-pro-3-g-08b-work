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
│       ├── env_loader.py
│       ├── logger_setup.py
│       └── sensor_client.py
├── server/                    # サーバー端末用
│   ├── logs/                  # 実行時に作成
│   │   └── sensor_server_YYYYMMDD-HHMMSS.log
│   ├── outputs/               # 実行時に作成
│   │   └── sensor_readings.csv
│   └── src/
│       ├── csv_writter.py
│       ├── env_loader.py
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
- `client/src/env_loader.py`, `server/src/env_loader.py`: `.env` の読み込みと必須設定の確認を行う共通処理
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

## セットアップ

このプロジェクトは `pyproject.toml` に依存ライブラリを定義しています。

仮想環境を作成して有効化したあと、リポジトリのルートディレクトリで次のコマンドを実行すると、必要なライブラリをインストールできます。

```bash
pip install .
```

インストール後は、`sensor-receiver`、`sensor-dashboard`、`sensor-client` の3つのコマンドを使用できます。

## 開発者向けメモ

### `pyproject.toml` について

`pyproject.toml` は、このプロジェクトのパッケージ設定ファイルです。

主に次の内容を定義しています。

- 使用するPythonのバージョン
- `Flask` や `python-dotenv` などの依存ライブラリ
- `pip install .` でインストールしたときに使えるコマンド

このプロジェクトでは、次の3つのコマンドを `pyproject.toml` で定義しています。

```toml
[project.scripts]
sensor-client = "client.src.sensor_client:main"
sensor-receiver = "server.src.sensor_receiver:main"
sensor-dashboard = "server.src.web_dashboard:main"
```

例えば `sensor-client` を実行すると、`client/src/sensor_client.py` の `main()` 関数が呼び出されます。

### `__init__.py` について

`__init__.py` は、そのディレクトリをPythonのパッケージとして扱うためのファイルです。

このプロジェクトでは、`client/` や `server/` 配下のコードを `pyproject.toml` のコマンドから呼び出せるようにするために置いています。

中身が空でも意味があります。削除すると、`sensor-client`、`sensor-receiver`、`sensor-dashboard` から各プログラムを正しく読み込めなくなる可能性があります。

### テストコードについて

テストコードは、プログラムの一部だけを自動で実行し、期待通りに動くか確認するためのコードです。

現在は主に次の内容を確認しています。

- クライアント側のDHT22読み取り処理
- クライアント側の送信失敗時のCSV保存
- サーバー側の `OK`、`WARNING`、`ERROR` 判定
- サーバー側のJSON解析とCSV保存
- `.env` の読み込みと必須項目チェック
- Webダッシュボードの表示とCSVダウンロード

テストを実行するには、開発用の依存ライブラリをインストールします。

```bash
pip install ".[dev]"
```

その後、リポジトリのルートディレクトリで次のように実行します。

```bash
python -m pytest
```

実機のDHT22センサーや実際のTCP通信を使わずに確認できるよう、テスト内では一部の処理をテスト用の仮実装に置き換えています。

## 実行方法

実行前に、設定ファイルを作成します。

```bash
cp client/src/.env.example client/src/.env
cp server/src/.env.example server/src/.env
```

`client/src/.env` の `SERVER_IP` には、データを受信するサーバー端末のIPアドレスを設定します。`RPI_ID` にはRaspberry Piの識別番号、`SENSOR_ID` にはセンサーの識別番号を設定します。

`server/src/.env` の `SERVER_IP` はセンサー受信用サーバーの待ち受けアドレス、`PORT_NUMBER` は待ち受けポートです。通常は `.env.example` のように `SERVER_IP = "0.0.0.0"` のままで使用できます。

各プログラムは起動時に `.env` の有無と必須項目を確認します。`.env` が存在しない場合、必要な項目が不足している場合、ポート番号が整数でない場合は、ログを出力して終了します。

### センサー受信サーバーを起動する

サーバー端末で、Raspberry Piから送信されるセンサーデータを受信するプログラムを起動します。

```bash
sensor-receiver
```

受信したデータは `server/outputs/sensor_readings.csv` に保存されます。

### Webダッシュボードを起動する

サーバー端末で、CSVに保存されたデータをWebブラウザから確認するためのダッシュボードを起動します。

```bash
sensor-dashboard
```

`server/src/.env` の設定が `.env.example` のままの場合、ブラウザで次のURLにアクセスします。

```text
http://サーバー端末のIPアドレス:5001/
```

同じ端末から確認する場合は、次のURLでもアクセスできます。

```text
http://127.0.0.1:5001/
```

### センサークライアントを起動する

DHT22センサーを接続したRaspberry Pi側で、センサー値を読み取ってサーバーへ送信するプログラムを起動します。

```bash
sensor-client
```

送信に失敗したデータや、DHT22センサーの読み取りに失敗したデータは `client/outputs/failed_sensor_readings.csv` に保存されます。

## Raspberry Piでの自動起動設定

`systemd/iot-sensor_client.service` は、Raspberry Pi起動時に `client/src/sensor_client.py` を自動実行するためのserviceファイルです。

前提:

- Raspberry Pi上のリポジトリ配置先: `/home/raspi4/iot-dev-pro-3-g-08b-work`
- 仮想環境: `/home/raspi4/iot-dev-pro-3-g-08b-work/venv`
- 実行ユーザー: `raspi4`
- 設定ファイル: `client/src/.env`

`client/src/.env` は `client/src/.env.example` を参考に作成します。

```env
SERVER_IP = "10.192.000.0"
PORT_NUMBER = 8765
RPI_ID = "raspi_000"
SENSOR_ID = "dht_0"
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

PC側では、Raspberry Piからの送信を受けるために `sensor-receiver` を起動しておきます。
