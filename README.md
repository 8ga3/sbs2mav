# sbs2mav
Convert SBS-1 CSV format data to MAVLink message.

## Overview

ADS-Bを受信し、MAVLinkで利用できるようにします。
付近を飛行している航空機を表示します。
Python 3.10と[pymavlink](https://github.com/ArduPilot/pymavlink)で動作確認しています。

## Install

[RTL-SDR](https://www.rtl-sdr.com/)の[DONGLE](https://www.rtl-sdr.com/buy-rtl-sdr-dvb-t-dongles/)をPCに接続し、[dump1090-fa](https://github.com/flightaware/dump1090)を使用してSBS-1をTCP/IPで配信します。
sbs2mavはsbsを変換し、MAVLink の[ADSB_VEHICLE](https://mavlink.io/en/messages/common.html#ADSB_VEHICLE)を配信します。

### macOS Venturaにインストール

```Shell
$ git clone git@github.com:flightaware/dump1090.git
$ cd dump1090
$ brew install librtlsdr
$ brew install libbladerf
$ brew install hackrf
$ brew install pkg-config
$ make
```

### 動作確認（ウェブブラウザ表示）

ローカル環境にウェブサーバーを実行します。
```Shell
$ mkdir public_html/data
$ cd public_html && python -m http.server 8090
```

別のterminalを立ち上げ、dump1090を実行します。
```Shell
$ ./dump1090 --write-json public_html/data >> log.txt
```

お好みのウェブブラウザで[http://[::]:8090/](http://[::]:8090/)を表示します。

### Install pymavlink

```Shell
$ pip3 install pymavlink
```

## 使い方

terminalを３つ動かしておきます。

### 1つ目
```Shell
$ dump1090 --net
```

受信しているADS-Bの内容を表示。

### 2つ目
```Shell
$ python3 sbs2mav.py
```

SBS-1をデコードしたものを表示。

### 3つ目
```Shell
$ python3 client.py
```

MAVLink ADSB_VEHICLEを表示。

[QGC](http://qgroundcontrol.com/)にはdump1090を直接読み込む機能がありますが、MAVLinkメッセージを送り込むことでも航空機が画面に表示できます。

## Reference

https://mavlink.io/
http://woodair.net/
https://www.rtl-sdr.com/
https://github.com/flightaware/dump1090
https://github.com/ArduPilot/pymavlink
http://qgroundcontrol.com/
https://gist.github.com/fasiha/c123a9c6b6c78df7597bb45e0fed808f
