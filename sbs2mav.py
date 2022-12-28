#!/usr/bin/env python3
import io
import os
import csv
import socket
import asyncio
from datetime import datetime, timezone
from tzlocal import get_localzone
from dateutil import parser, tz
from pymavlink import mavutil

# export MAVLINK20=1
os.environ['MAVLINK20'] = '1'

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

class SbsModel:
    """Kinetic Avionic Products製品SBSのBaseStationソフトウェア互換のプロトコル・モデルクラス
    """

    def __init__(self) -> None:
        self.zone = tz.gettz(str(get_localzone()))
        self.vehicles = {}

    def set_vehicles(self, csv) -> None:
        for line in csv:
            msg_type = line[0]
            if msg_type == 'MSG':
                # tx_type = line[1]
                hex_ident = line[4]
                veh = self.vehicles.setdefault(hex_ident, {})
                self.vehicles[hex_ident] = self.set_vehicle(veh, line)

    def set_vehicle(self, veh: dict, line: str) -> dict:
        veh['update'] = True

        gen_date = line[6]
        gen_time = line[7]
        log_date = line[8]
        log_time = line[9]

        veh['datetime_gen'] = parser.parse(f'{gen_date} {gen_time}').astimezone(self.zone)
        veh['datetime_log'] = parser.parse(f'{log_date} {log_time}').astimezone(self.zone)

        if 'callsign' not in veh.keys(): veh['callsign'] = '        '

        if line[10]: veh['callsign'] = line[10]
        if line[11]: veh['alt'] = int(line[11])
        if line[12]: veh['gs'] = int(line[12])
        if line[13]: veh['track'] = int(line[13])
        if line[14]: veh['lat'] = float(line[14])
        if line[15]: veh['lon'] = float(line[15])
        if line[16]: veh['vrate'] = int(line[16])
        if line[17]: veh['squawk'] = int(line[17])
        if line[18]: veh['alert'] = int(line[18])
        if line[19]: veh['emergency'] = int(line[19])
        if line[20]: veh['spi'] = int(line[20])
        if line[21]: veh['gnd'] = int(line[21])

        return veh

    def clear_update_flag(self) -> None:
        for v in self.vehicles.values():
            v['update'] = False

    def delete_lost_aircraft(self, timeout: int = 30) -> None:
        now = datetime.now(timezone.utc)
        self.vehicles = {k: v for k, v in self.vehicles.items() if (now - v["datetime_gen"]).total_seconds() < timeout}

    def make_str(self, k: str, v: dict, d: float) -> str:
        val: str = lambda v, name: v[name] if name in v.keys() else "-"
        valm: str = lambda v, name, multi: int(v[name] * multi) if name in v.keys() else "-"

        return f'{"*" if v.get("update") else " "}' \
            f'ModeS:{k} {d:8.5f}' \
            f' MG:{v.get("datetime_gen").strftime("%x %X")}' \
            f' CS:{v.get("callsign"):8}' \
            f' Alt:{val(v, "alt")}ft/{valm(v, "alt", 0.3048)}m' \
            f' Lat:{val(v, "lat")}' \
            f' Lon:{val(v, "lon")}' \
            f' SP:{val(v, "gs")}kts/{valm(v, "gs", 1.852)}km/h' \
            f' TR:{val(v, "track")}°' \
            f' VR:{val(v, "vrate")}fpm/{valm(v, "vrate", 0.3048)}m' \
            f' SQ:{v.get("squawk")}' \
            f' ALERT:{val(v, "alert")}' \
            f' Emg:{val(v, "emergency")}' \
            f' SPI:{val(v, "spi")}' \
            f' GND:{val(v, "gnd")}'

    def __str__(self) -> str:
        prt = ''
        now = datetime.now(timezone.utc)
        for k, v in self.vehicles.items():
            d = (now - v["datetime_gen"]).total_seconds()
            if len(prt):
                prt += '\n'
            prt += self.make_str(k, v, d)
        return prt


class SbsClient:
    """Kinetic Avionic Products製品SBSのBaseStationソフトウェア互換のプロトコルクライアント
    """

    BUF_SIZE = 4096 * 4

    def __init__(self, model: SbsModel, host: str = 'localhost', port: int = 30003) -> None:
        self.model = model
        self.host = host
        self.port = port

    async def __aenter__(self):
        while True:
            try:
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                break
            except socket.error as e:
                await asyncio.sleep(1)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.writer.close()
        await self.writer.wait_closed()

    async def recv(self) -> bool:
        data = await self.reader.read(self.BUF_SIZE)
        if not data:
            return False
        csv_reader = self.perse_csv(data.decode())
        self.model.set_vehicles(csv_reader)
        return True

    def perse_csv(self, data: str):
        f = io.StringIO()
        f.write(data)
        f.seek(0)
        csv_reader = csv.reader(f)
        return csv_reader


async def main_sbs(model: SbsModel, host: str = 'localhost', port: int = 30003):
    async with SbsClient(model, host, port) as sbs:
        print('connect!')
        while True:
            ret = await sbs.recv()
            if not ret:
                break
            print('')
            print(model)
            model.delete_lost_aircraft()

            await asyncio.sleep(0.1)


def send_heartbeat(mav):
    '''Heartbeatを1Hzで送信
    Heartbeatを最低1回は送らないと受信できない
    '''
    mav.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_ADSB,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE)

def send_adsb_vehicle(mav, hex_id: str, sbs: dict, d: int):
    '''Send ADSB_VEHICLE'''
    lat, lon, heading, altitude, altitude_type, heading = 0, 0, 0, 0, 0, 0
    hor_velocity, ver_velocity, tslc, flags, squawk = 0, 0, 0, 0, 0
    emitter_type = mavutil.mavlink.ADSB_EMITTER_TYPE_NO_INFO
    ICAO_address = int(hex_id, 16)
    callsign = sbs['callsign']
    tslc = d

    if callsign != '        ':
        flags |= mavutil.mavlink.ADSB_FLAGS_VALID_CALLSIGN
    if 'lat' in sbs.keys() and 'lon' in sbs.keys():
        # lat * 10**7 (degE7)
        flags |= mavutil.mavlink.ADSB_FLAGS_VALID_COORDS
        lat = int(sbs['lat'] * 10**7)
        lon = int(sbs['lon'] * 10**7)
    if 'alt' in sbs.keys():
        # Convert feet to millimeters
        flags |= mavutil.mavlink.ADSB_FLAGS_VALID_ALTITUDE
        flags |= mavutil.mavlink.ADSB_FLAGS_BARO_VALID
        altitude_type = mavutil.mavlink.ADSB_ALTITUDE_TYPE_PRESSURE_QNH
        altitude = int(sbs['alt'] * 0.3048 * 1000)
    if 'track' in sbs.keys():
        # 0~359.99° * 100 (cdeg)
        flags |= mavutil.mavlink.ADSB_FLAGS_VALID_HEADING
        heading = sbs['track'] * 100
    if 'gs' in sbs.keys():
        # Convert from kts to cm/s
        flags |= mavutil.mavlink.ADSB_FLAGS_VALID_VELOCITY
        hor_velocity = int((sbs['gs'] * 1.852 * 1000 * 100) / 3600)
    if 'vrate' in sbs.keys():
        # Convert from f/m to cm/s
        flags |= mavutil.mavlink.ADSB_FLAGS_VERTICAL_VELOCITY_VALID
        ver_velocity = int(sbs['vrate'] * 0.3048 * 100 / 60)
    if 'squawk' in sbs.keys():
        flags |= mavutil.mavlink.ADSB_FLAGS_VALID_SQUAWK
        squawk = sbs['squawk']

    mav.mav.adsb_vehicle_send(ICAO_address, lat, lon, altitude_type,
        altitude, heading, hor_velocity, ver_velocity, callsign.encode(),
        emitter_type, tslc, flags, squawk)

async def cycle_recv(mav):
    '''Receiving'''
    type = ['HEARTBEAT']
    msg = mav.recv_match(type=type, blocking=False)
    # msg = mav.recv_msg()

    if (msg is None) or (msg.get_type() == 'BAD_DATA'):
        pass
    # else:
    #     print("(sys:%u comp:%u) %s" % (msg.get_srcSystem(), msg.get_srcComponent(), msg.get_type()))

async def main_mav(model: SbsModel, device):
    loop = asyncio.get_running_loop()
    heartbeat_wait_time = 1.0
    heartbeat_end_time = 0

    mav = mavutil.mavlink_connection(device, source_system=1,
        source_component=mavutil.mavlink.MAV_COMP_ID_ADSB)

    while True:
        time_now = loop.time()
        if time_now >= heartbeat_end_time:
            heartbeat_end_time = time_now + heartbeat_wait_time
            send_heartbeat(mav)

            now = datetime.now(timezone.utc)
            for k, v in model.vehicles.items():
                d = int((now - v["datetime_gen"]).total_seconds())
                send_adsb_vehicle(mav, k, v, d)
            model.delete_lost_aircraft()
            model.clear_update_flag()

        await cycle_recv(mav)
        await asyncio.sleep(0.2)


if __name__ == "__main__":
    # device = 'udpin:localhost:14540' # PX4 Simulatorに送信
    device = 'udpout:localhost:14550' # clientに直接送信
    host = 'localhost'
    port = 30003
    model = SbsModel()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tasks = [
        main_mav(model, device),
        main_sbs(model, host, port)
    ]

    try:
        asyncio.run(asyncio.wait(tasks))
        # loop.run_until_complete(asyncio.wait(tasks))
    except KeyboardInterrupt:
        pass
    finally:
        if loop.is_running():
            loop.shutdown_default_executor()

    print('finish!')
