# IoTデバイスプログラミング３（2026）G-08B

## ファイル階層

```text
.
├── README.md
├── requirements.txt
├── Android/                   # Android端末用
│   └── index.html
├── client/                    # センサー接続端末用
│   ├── logs/                  # 実行時に作成
│   │   └── sensor_client_YYYYMMDD-HHMMSS.log
│   ├── outputs/               # 実行時に作成
│   │   └── failed_sensor_readings.csv
│   └── src/
│       ├── csv_writter.py
│       ├── dht22_takemoto.py
│       ├── logger_setup.py
│       └── sensor_client.py
└── server/                    # サーバー端末用
    ├── logs/                  # 実行時に作成
    │   └── sensor_server_YYYYMMDD-HHMMSS.log
    ├── outputs/               # 実行時に作成
    │   └── sensor_readings.csv
    └── src/
        ├── csv_writter.py
        ├── logger_setup.py
        ├── sensor_receiver.py
        ├── web_dashboard.py
        └── templates/
            └── dashboard.html
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
