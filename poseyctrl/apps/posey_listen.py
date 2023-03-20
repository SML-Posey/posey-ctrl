from logging import getLogger

import argparse
import logging
import traceback
from multiprocess import Queue
import bleak
import datetime as dt

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement

from poseyctrl import csvw
from poseyctrl.sensor import PoseySensor

def posey_listen():

    # Process arguments.
    device_names = []
    parser = argparse.ArgumentParser("posey-listen", description="Listens to a posey device.")
    parser.add_argument("sensor",
        type=str, help="Sensor to connect to.")
    parser.add_argument("-t", "--timeout",
        type=float, default=10,
        help="Timeout (seconds) to scan for BLE sensor devices.")
    parser.add_argument("-d", "--debug",
        action="store_true", default=False,
        help="Enable debug logging.")
    args = parser.parse_args()

    # Configure logger.
    logging.basicConfig(
        handlers=[
            logging.FileHandler(
                f"posey-listen-{args.sensor}-{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ],
        datefmt='%H:%M:%S',
        format='{name:.<15} {asctime}: [{levelname}] {message}',
        style='{', level=logging.DEBUG if args.debug else logging.INFO)
    log = getLogger("main")
    getLogger("asyncio").setLevel(logging.CRITICAL)

    device_name = args.sensor

    log.info(f"Start time: {dt.datetime.now().astimezone().replace(microsecond=0).isoformat()}")
    log.info(f"Sensor: {device_name}")
    log.info(f"Scan timeout: {args.timeout}")

    # Config.
    qin = Queue()
    qout = Queue()
    pq = Queue()

    csvwriter = csvw.CSVWriter(qin)

    # Find sensors.
    log.info(f"Scanning for Posey sensor {device_name}...")
    ble = BLERadio()
    device_adv = None
    for adv in ble.start_scan(Advertisement, timeout=args.timeout):
        if adv.complete_name is None:
            continue
        cn = adv.complete_name.lower()
        if ("posey" in cn) and (device_name.lower() in cn):
            name = adv.complete_name
            log.info(f"Found Posey {name} (Address: {adv.address.string})")
            device_adv = adv
            ble.stop_scan()
            break
    
    if device_adv is None:
        log.error("Device not found!")
        raise RuntimeError("Could not find Posey sensor!")
    
    device_name = device_adv.complete_name

    log.info(f"Connecting to {device_adv.complete_name}.")
    sensor = PoseySensor(device_name, ble, device_adv, qout, qin, pq)
    log.info(f"Connecting to device {sensor}")
    if sensor.connect():
        log.info(" - Connected.")
    else:
        log.error(" - Failed to connect to BLE device.")
        raise RuntimeError("Could not connect to Posey sensor!")

    try:
        while True:
            # Connected?
            if not sensor.connected:
                log.warning(f"Sensor {sensor.name} disconnected. Reconnecting...")
                try:
                    sensor.connect()
                except KeyboardInterrupt:
                    raise
                except bleak.exc.BleakError as e:
                    msg = e.message if hasattr(e, 'message') else e
                    log.warning(f"Bleak error: {msg}")
                except:
                    log.info("Exception on connect:")
                    traceback.print_exc()

                if sensor.connected:
                    log.info("Reconnect successful")
                else:
                    log.error(f"Could not reconnect to {sensor.name}!")
                    continue

            # Collect data.
            sensor.hil.process_uart()

            # If time, print statistics.
            sensor.hil.stats.log_stats()

    except KeyboardInterrupt:
        log.info("Keyboard interrupt, breaking.")

    except:
        traceback.print_exc()

    log.info("Disconnecting sensor...")
    sensor.disconnect()
    sensor.hil.close()

if __name__ == "__main__":
    posey_listen()