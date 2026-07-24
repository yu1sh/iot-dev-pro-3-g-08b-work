# IoTデバイスプログラミング３（2026）G-08B

DHT22センサーで取得した温度・湿度をRaspberry Piからサーバーへ送信し、CSVへの保存とWebダッシュボードでの表示を行うシステムです。

## 構成

| ディレクトリ | 内容                               |
| ------------ | ---------------------------------- |
| `client/`  | センサー値の取得とサーバーへの送信 |
| `server/`  | データの受信、CSV保存、Web表示     |
| `mobile-web/` | モバイル端末からダッシュボードを開くためのHTML |
| `systemd/` | Raspberry Pi・サーバー自動起動用service |
| `scripts/` | CIのテスト結果・カバレッジ集計     |
| `docs/`    | 技術資料と授業資料                 |

通信仕様、内部処理、テスト、運用方法の詳細は[技術資料](docs/技術資料.md)を参照してください。

## 必要環境

- Python 3.11以上
- DHT22を接続したRaspberry Pi（センサークライアントを実行する場合）

## セットアップ

リポジトリのルートディレクトリで、実行する役割に応じた依存ライブラリを
インストールします。

```bash
# 受信サーバーとWebダッシュボード
pip install ".[server]"

# Raspberry Piのセンサークライアント（lgpioを含む）
pip install ".[client]"

# dotenvなどの共通機能だけが必要な場合
pip install .
```

設定ファイルを作成します。

```bash
cp client/.env.example client/.env
cp server/.env.example server/.env
```

主な設定項目は次のとおりです。

| ファイル | 項目 | 必須 | 内容 |
| --- | --- | --- | --- |
| `client/.env` | `SERVER_IP` | 必須 | 送信先サーバーのIPアドレス |
| `client/.env` | `PORT_NUMBER` | 必須 | センサーデータ送信先ポート |
| `client/.env` | `RPI_ID` | 必須 | Raspberry Piの識別子 |
| `client/.env` | `SENSOR_ID` | 必須 | センサーの識別子 |
| `client/.env` | `GPIO_NUMBER` | 必須 | DHT22のデータ線を接続するGPIO番号 |
| `client/.env` | `CSV_FILE` | 任意 | 失敗データCSV。既定値は`outputs/failed_sensor_readings.csv` |
| `client/.env` | `LOG_DIR` | 任意 | ログ保存先。既定値は`logs` |
| `server/.env` | `SERVER_IP` | 必須 | センサー受信サーバーの待受アドレス |
| `server/.env` | `PORT_NUMBER` | 必須 | センサーデータの待受ポート |
| `server/.env` | `CSV_FILE` | 任意 | 受信データCSV。既定値は`outputs/sensor_readings.csv` |
| `server/.env` | `LOG_DIR` | 任意 | ログ保存先。既定値は`logs` |
| `server/.env` | `DEBUG_MODE` | 任意 | Webダッシュボードのデバッグ設定。既定値は`false` |

`CSV_FILE`と`LOG_DIR`に相対パスを指定した場合は、それぞれの`.env`がある
ディレクトリを基準に解決します。同名のプロセス環境変数がある場合は、その値が
`.env`より優先されます。

## 実行方法

センサー受信サーバー：

```bash
sensor-receiver
# 一時的に待受アドレスとポートを上書きする場合
sensor-receiver -h 0.0.0.0 -p 8765
```

Webダッシュボード：

```bash
sensor-dashboard
```

センサークライアント：

```bash
sensor-client
# 一時的に送信先とポートを上書きする場合
sensor-client -h 192.0.2.10 -p 8765
```

Webダッシュボードは、標準設定では次のURLから確認できます。

```text
http://サーバー端末のIPアドレス:5001/
```

同じ端末から確認する場合：

```text
http://127.0.0.1:5001/
```

ダッシュボードには次の機能があります。

- 温度・湿度の全データ平均と、各行の1つ前のデータとの差の表示
- 5秒ごとの自動更新
- 見出しクリックによる列の昇順・降順ソート（数値を考慮）
- 自動更新後も同じ並びを適用する、タブ単位のソート状態保持
- 「確認」ボタンによる確認メッセージの表示
- `/files`からの受信データCSVダウンロード
- `/files/import`への`failed_sensor_readings.csv`取り込み

平均値は、CSV内の空欄ではない温度・湿度をそれぞれ対象として小数第1位まで
表示します。前データ差はCSV上で直前にある行との差で、先頭行は`-`です。
「確認」ボタンは画面に「確認しました」と表示するだけで、CSVの内容は変更しません。

アップロードできるファイルは2 MiB以下のCSVです。CSVはUTF-8、所定の6列、
`YYYYMMDD-HHMMSS`形式の日時、対応ステータスを満たす必要があります。

`mobile-web/index.html`は、モバイル端末からダッシュボードを開くためのリンクです。
ファイル内のIPアドレスを実際のサーバーアドレスに変更してから使用してください。

## データ形式

クライアントは1測定を1要素のJSON配列にし、末尾に改行を付けたNDJSONとして
送信します。測定間隔は10秒です。サーバーはCSV保存後に`message_id`付きACKを
返し、同じID・同じ内容の再送は二重保存しません。

CSVはクライアント・サーバー共通で次の6列です。

```text
timestamp,raspi_id,dht_temp,dht_humid,sensor_id,status
```

`timestamp`はローカル時刻の`YYYYMMDD-HHMMSS`形式です。`status`は
`OK`、`WARNING`、`ERROR`、`SEND_FAILED`のいずれかです。

## 出力先

| ファイル                                      | 内容                                   |
| --------------------------------------------- | -------------------------------------- |
| `server/outputs/sensor_readings.csv`        | サーバーが受信したセンサーデータ       |
| `client/outputs/failed_sensor_readings.csv` | センサー取得または送信に失敗したデータ |
| `server/logs/`                              | サーバーログ                           |
| `client/logs/`                              | クライアントログ                       |

## Raspberry Piでの自動起動

`systemd/iot-sensor_client.service.example`をコピーし、`User`、
`WorkingDirectory`、`ExecStart`を実際の環境に合わせて変更したうえで登録します。

```bash
sudo cp systemd/iot-sensor_client.service.example \
  /etc/systemd/system/iot-sensor_client.service
sudo systemctl daemon-reload
sudo systemctl enable --now iot-sensor_client.service
```

## サーバーでの自動起動

センサーデータ受信とWebダッシュボードは別プロセスで動作するため、それぞれ
独立したserviceとして登録します。別環境へ導入する場合は、2つの`.example`を
コピーし、`User`、`WorkingDirectory`、`ExecStart`を実際の環境に合わせて
変更します。

```bash
sudo cp systemd/iot-sensor_receiver.service.example \
  /etc/systemd/system/iot-sensor_receiver.service
sudo cp systemd/iot-sensor_dashboard.service.example \
  /etc/systemd/system/iot-sensor_dashboard.service

sudo systemctl daemon-reload
sudo systemctl enable --now \
  iot-sensor_receiver.service \
  iot-sensor_dashboard.service
```

起動状態とログは次のコマンドで確認できます。

```bash
systemctl status iot-sensor_receiver.service
systemctl status iot-sensor_dashboard.service
journalctl -u iot-sensor_receiver.service
journalctl -u iot-sensor_dashboard.service
```

## テスト

```bash
pip install ".[dev]"
python -m pytest --cov=client/src --cov=server/src --cov-branch
```

CIではPython 3.11から3.14で、単体テスト、ローカルTCP結合テスト、
実Flaskテスト、並行CSV書き込みテスト、依存関係検査、構文検査を実行します。
カバレッジが90%未満の場合は失敗します。
