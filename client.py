#!/usr/bin/env python3
import os
import asyncio
import argparse
from pymavlink import mavutil

# export MAVLINK20=1
os.environ['MAVLINK20'] = '1'

class Color:
	BLACK          = '\033[30m' #(文字)黒
	RED            = '\033[31m' #(文字)赤
	GREEN          = '\033[32m' #(文字)緑
	YELLOW         = '\033[33m' #(文字)黄
	BLUE           = '\033[34m' #(文字)青
	MAGENTA        = '\033[35m' #(文字)マゼンタ
	CYAN           = '\033[36m' #(文字)シアン
	WHITE          = '\033[37m' #(文字)白
	COLOR_DEFAULT  = '\033[39m' #文字色をデフォルトに戻す
	BOLD           = '\033[1m'  #太字
	UNDERLINE      = '\033[4m'  #下線
	INVISIBLE      = '\033[08m' #不可視
	REVERCE        = '\033[07m' #文字色と背景色を反転
	BG_BLACK       = '\033[40m' #(背景)黒
	BG_RED         = '\033[41m' #(背景)赤
	BG_GREEN       = '\033[42m' #(背景)緑
	BG_YELLOW      = '\033[43m' #(背景)黄
	BG_BLUE        = '\033[44m' #(背景)青
	BG_MAGENTA     = '\033[45m' #(背景)マゼンタ
	BG_CYAN        = '\033[46m' #(背景)シアン
	BG_WHITE       = '\033[47m' #(背景)白
	BG_DEFAULT     = '\033[49m' #背景色をデフォルトに戻す
	RESET          = '\033[0m'  #全てリセット

# Heartbeatを1Hzで送信
# Heartbeatを最低１回は送らないと受信できない
async def cycle_heartbeat_send(mav):
    mav.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED | mavutil.mavlink.MAV_MODE_FLAG_MANUAL_INPUT_ENABLED,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE)

# Receiving
async def cycle_recv(mav):
    '''reciver'''
    msg = mav.recv_match(type=['HEARTBEAT', 'ADSB_VEHICLE'], blocking=False)
    # msg = mav.recv_msg()
    if (msg is None) or (msg.get_type() == 'BAD_DATA'):
        pass
    elif msg.get_type() == 'HEARTBEAT':
        print(f'(system {msg.get_srcSystem()} component {msg.get_srcComponent()}) {msg.get_type()}')
    elif msg.get_type() == 'MESSAGE_INTERVAL':
        dict = msg.to_dict()
        print(f'(system {msg.get_srcSystem()} component {msg.get_srcComponent()}) {msg.get_type()} message_id={dict["message_id"]} interval_us={dict["interval_us"]}')
    elif msg.get_type() == 'UAVIONIX_ADSB_TRANSCEIVER_HEALTH_REPORT':
        dict = msg.to_dict()
        print(f'(system {msg.get_srcSystem()} component {msg.get_srcComponent()}) {msg.get_type()} rfHealth={dict["rfHealth"]}')
    elif msg.get_type() == 'ADSB_VEHICLE':
        print(f'(system {msg.get_srcSystem()} component {msg.get_srcComponent()}) {msg.get_type()}', end=' ')

        dict = msg.to_dict()
        flags = dict["flags"]
        print(f'ModeS:{dict["ICAO_address"]:06X}', end=' ')
        print(f'{dict["tslc"]:2}s', end=' ')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VALID_CALLSIGN:
            print(f'{Color.MAGENTA}', end='')
        print(f'CS:{dict["callsign"]: <8}', end=' ')
        print(f'{Color.RESET}', end='')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VALID_ALTITUDE:
            print(f'{Color.MAGENTA}', end='')
        print(f'Alt:{int(dict["altitude"] / 1000):5}m', end=' ')
        print(f'{Color.RESET}', end='')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VALID_COORDS:
            print(f'{Color.MAGENTA}', end='')
        print(f'Lat:{dict["lat"] / 10**7:8.5f}', end=' ')
        print(f'Lon:{dict["lon"] / 10**7:9.5f}', end=' ')
        print(f'{Color.RESET}', end='')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VALID_VELOCITY:
            print(f'{Color.MAGENTA}', end='')
        print(f'SP:{int(dict["hor_velocity"] * 3600 / (1000 * 100)):3}km/h', end=' ')
        print(f'{Color.RESET}', end='')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VALID_HEADING:
            print(f'{Color.MAGENTA}', end='')
        print(f'TR:{int(dict["heading"] / 100):3}°', end=' ')
        print(f'{Color.RESET}', end='')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VERTICAL_VELOCITY_VALID:
            print(f'{Color.MAGENTA}', end='')
        print(f'VR:{int(dict["ver_velocity"] / 100):3}m/s', end=' ')
        print(f'{Color.RESET}', end='')
        if not flags & mavutil.mavlink.ADSB_FLAGS_VALID_SQUAWK:
            print(f'{Color.MAGENTA}', end='')
        print(f'SQ:{dict["squawk"]:4}', end=' ')
        print(f'{Color.RESET}', end='')
        print(f'FL:{flags:#018b}')
    else:
        print("(system %u component %u) %s" % (msg.get_srcSystem(), msg.get_srcComponent(), msg.get_type()))

async def main(mav):
    loop = asyncio.get_running_loop()
    heartbeat_wait_time = 1.0
    heartbeat_end_time = 0

    while True:
        time_now = loop.time()
        if time_now >= heartbeat_end_time:
            heartbeat_end_time = time_now + heartbeat_wait_time
            await cycle_heartbeat_send(mav)

        await cycle_recv(mav)
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse command line options.')
    parser.add_argument('-d', '--device', type=str, default='udpin:localhost:14550', help='device name. (ex. "udpin:localhost:14550", "tcp:localhost:5763", "/dev/tty.usbserial-0001")')
    parser.add_argument('-b', '--baud', type=int, default=57600, help='baudrate. default=57600')
    args = parser.parse_args()

    # device = 'tcp:localhost:5763' # Ardupilot Simulatorから受信
    # device = 'udpin:localhost:14550' # PX4 Simulatorから受信
    # device = '/dev/tty.usbserial-0001'
    device = args.device
    baud = args.baud

    mav = mavutil.mavlink_connection(device, baud=baud, source_system=255, source_component=1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        asyncio.run(main(mav))
    except KeyboardInterrupt:
        pass
    finally:
        if loop.is_running():
            loop.shutdown_default_executor()
