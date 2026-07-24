# IoTデバイスプログラミング３（2026）G-08B

DHT22センサーで取得した温度・湿度をRaspberry Piからサーバーへ送信し、CSVへの保存とWebダッシュボードでの表示を行うシステムです。

## 構成

| ディレクトリ | 内容                               |
| ------------ | ---------------------------------- |
| `client/`  | センサー値の取得とサーバーへの送信 |
| `server/`  | データの受信、CSV保存、Web表示     |
| `Android/` | Android端末用HTML                  |
| `systemd/` | Raspberry Pi自動起動用service      |

通信仕様、内部処理、テスト、運用方法の詳細は[技術資料](docs/技術資料.md)を参照してください。

## 必要環境

- Python 3.11以上
- DHT22を接続したRaspberry Pi（センサークライアントを実行する場合）

## セットアップ

リポジトリのルートディレクトリで依存ライブラリをインストールします。

```bash
pip install .
```

設定ファイルを作成します。

```bash
cp client/.env.example client/.env
cp server/.env.example server/.env
```

主な設定項目は次のとおりです。

| ファイル            | 項目            | 内容                               |
| ------------------- | --------------- | ---------------------------------- |
| `client/.env` | `SERVER_IP`   | 送信先サーバーのIPアドレス         |
| `client/.env` | `PORT_NUMBER` | センサーデータ送信先ポート         |
| `client/.env` | `RPI_ID`      | Raspberry Piの識別子               |
| `client/.env` | `SENSOR_ID`   | センサーの識別子                   |
| `server/.env` | `SERVER_IP`   | センサー受信サーバーの待受アドレス |
| `server/.env` | `PORT_NUMBER` | センサーデータの待受ポート         |
| `server/.env` | `DEBUG_MODE`  | Webダッシュボードのデバッグ設定    |

## 実行方法

センサー受信サーバー：

```bash
sensor-receiver
```

Webダッシュボード：

```bash
sensor-dashboard
```

センサークライアント：

```bash
sensor-client
```

Webダッシュボードは、標準設定では次のURLから確認できます。

```text
http://サーバー端末のIPアドレス:5001/
```

同じ端末から確認する場合：

```text
http://127.0.0.1:5001/
```

## 出力先

| ファイル                                      | 内容                                   |
| --------------------------------------------- | -------------------------------------- |
| `server/outputs/sensor_readings.csv`        | サーバーが受信したセンサーデータ       |
| `client/outputs/failed_sensor_readings.csv` | センサー取得または送信に失敗したデータ |
| `server/logs/`                              | サーバーログ                           |
| `client/logs/`                              | クライアントログ                       |

## テスト

```bash
pip install ".[dev]"
python -m pytest --cov=client/src --cov=server/src --cov-branch
```

CIではPython 3.11から3.14で、単体テスト、ローカルTCP結合テスト、
実Flaskテスト、並行CSV書き込みテスト、依存関係検査、構文検査を実行します。
カバレッジが90%未満の場合は失敗します。
