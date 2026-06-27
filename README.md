# IoTデバイスプログラミング３（2026）G-08B

## ファイル階層

```text
.
├── README.md
├── requirements.txt
├── Android/
│   └── index.html
├── client/
│   ├── logs/                  # 実行時に作成
│   │   └── sensor_client_YYYYMMDD-HHMMSS.log
│   └── src/
│       ├── dht22_takemoto.py
│       ├── logger_setup.py
│       └── sensor_client.py
└── server/
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

- `client/src/`: センサー側で動作するクライアントプログラム
- `server/src/`: センサーデータの受信・記録・Web表示を行うサーバープログラム
- `server/src/templates/`: Webダッシュボード用のHTMLテンプレート
- `Android/`: Android表示用のHTMLファイル
- `client/logs/`: クライアント実行時に作成されるログ保存先
- `server/logs/`: サーバー実行時に作成されるログ保存先
- `server/outputs/`: 受信したセンサーデータのCSV保存先
