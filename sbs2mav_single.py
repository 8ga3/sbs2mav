#!/usr/bin/env python3
import io
import csv
import socket
from datetime import datetime, timezone
from tzlocal import get_localzone
from dateutil import parser, tz

HOST = '127.0.0.1'
PORT = 30003 # ポート番号
BUF_SIZE = 4096 * 4

zone = tz.gettz(str(get_localzone()))

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))


# http://woodair.net/sbs/article/barebones42_socket_data.htm
#
# Field 1:  Message type            (MSG, STA, ID, AIR, SEL or CLK)
# Field 2:  Transmission Type       MSG sub types 1 to 8. Not used by other message types.
# Field 3:  Session ID              Database Session record number
# Field 4:  AircraftID              Database Aircraft record number
# Field 5:  HexIdent                Aircraft Mode S hexadecimal code
# Field 6:  FlightID                Database Flight record number
# Field 7:  Date message generated
# Field 8:  Time message generated
# Field 9:  Date message logged
# Field 10: Time message logged

# Field 11: Callsign                An eight digit flight ID - can be flight number or registration (or even nothing).
# Field 12: Altitude                Mode C altitude. Height relative to 1013.2mb (Flight Level). Not height AMSL..
# Field 13: GroundSpeed             Speed over ground (not indicated airspeed)
# Field 14: Track                   Track of aircraft (not heading). Derived from the velocity E/W and velocity N/S
# Field 15: Latitude                North and East positive. South and West negative.
# Field 16: Longitude               North and East positive. South and West negative.
# Field 17: VerticalRate            64ft resolution
# Field 18: Squawk                  Assigned Mode A squawk code.
# Field 19: Alert (Squawk change)   Flag to indicate squawk has changed.
# Field 20: Emergency               Flag to indicate emergency code has been set
# Field 21: SPI (Ident)             Flag to indicate transponder Ident has been activated.
# Field 22: IsOnGround              Flag to indicate ground squat switch is active

vehicles = {}

try:
    while True:
        data = sock.recv(BUF_SIZE).decode()
        if not data:
            break

        f = io.StringIO()
        f.write(data)
        f.seek(0)
        csv_reader = csv.reader(f)
        for line in csv_reader:
            msg_type = line[0]
            if msg_type == 'MSG':
                # tx_type = line[1]
                hex_ident = line[4]
                gen_date = line[6]
                gen_time = line[7]
                log_date = line[8]
                log_time = line[9]

                veh = vehicles.setdefault(hex_ident, {})
                veh['datetime_gen'] = parser.parse(f'{gen_date} {gen_time}').astimezone(zone)
                veh['datetime_log'] = parser.parse(f'{log_date} {log_time}').astimezone(zone)

                if 'callsign' not in veh.keys():
                    veh['callsign'] = ''

                if line[10] != '':
                    veh['callsign'] = line[10]
                if line[11] != '':
                    veh['alt'] = int(line[11])
                if line[12] != '':
                    veh ['gs'] = int(line[12])
                if line[13] != '':
                    veh ['track'] = int(line[13])
                if line[14] != '':
                    veh ['lat'] = float(line[14])
                if line[15] != '':
                    veh ['lon'] = float(line[15])
                if line[16] != '':
                    veh ['vrate'] = int(line[16])
                if line[17] != '':
                    veh['squawk'] = int(line[17])
                if line[18] != '':
                    veh['alert'] = int(line[18])
                if line[19] != '':
                    veh['emergency'] = int(line[19])
                if line[20] != '':
                    veh['spi'] = int(line[20])
                if line[21] != '':
                    veh['gnd'] = int(line[21])

                vehicles[hex_ident] = veh
            else:
                print(msg_type)

        now = datetime.now(timezone.utc)
        vehicles = {k: v for k, v in vehicles.items() if (now - v["datetime_gen"]).total_seconds() < 30}

        print('')
        for k, v in vehicles.items():
            delta = (now - v["datetime_gen"]).total_seconds()
            print(f'ModeS:{k} {delta:8.5f} MG:{v.get("datetime_gen").strftime("%x %X")}' \
                f' CS:{v.get("callsign"):8}' \
                f' Alt:{v["alt"] if "alt" in v.keys() else "-"}ft({int(v["alt"] / 3.281) if "alt" in v.keys() else "-"}m)' \
                f' Lat:{v["lat"] if "lat" in v.keys() else "-"}' \
                f' Lon:{v["lon"] if "lon" in v.keys() else "-"}' \
                f' {v["gs"] if "gs" in v.keys() else "-"}kts({int(v["gs"] * 1.852) if "gs" in v.keys() else "-"}km/h)' \
                f' {v["track"] if "track" in v.keys() else "-"}°' \
                f' VR:{v["vrate"] if "vrate" in v.keys() else "-"}fpm({int(v["vrate"] / 3.281) if "vrate" in v.keys() else "-"}m)' \
                f' SQ:{v.get("squawk")} ALERT:{v.get("alert")}' \
                f' Emg:{v.get("emergency")} SPI:{v.get("spi")} GND:{v.get("gnd")}')

except KeyboardInterrupt:
    sock.shutdown(socket.SHUT_RD)

sock.close()
print('finish!')
