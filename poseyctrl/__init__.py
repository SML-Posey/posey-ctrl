from logging import getLogger
import os


MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
VERSION = '1.1.0'

NameToAddressMap = {
    # BMD-350 dev board
    'dumbledork': '9191FDB5-E182-BE53-604C-83715F9E56BA',

    # v5
    'tangaray': '83958895-56AA-451B-7B43-146FBA93C568', # Waist - NAND

    # v6
    'rose': 'B3E7DBCA-5975-C10E-6CD0-F3EC0A99E32C', # Waist - NOR
    'lily': 'D5ACC31A-6F33-5688-E6B6-52E8C4EAB0C9', # Watch
    'lilac': '4CF77840-4450-D8EF-35E3-E7DBC4192CC2'# Watch
}
AddressToNameMap = {v: k for k, v in NameToAddressMap.items()}


def main():
    import argparse
    import logging
    import traceback
    from multiprocess import Process, Queue
    import queue
    import bleak
    import datetime

    # from numpy.core.fromnumeric import trace

    from adafruit_ble import BLERadio
    from adafruit_ble.advertising.standard import Advertisement

    from poseyctrl import csvw
    from poseyctrl.sensor import PoseySensor

    # Process arguments.
    device_names = list(NameToAddressMap.keys())
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-n", "--num-sensors",
        type=int,
        help="Maximum number of sensors to connect to.")
    group.add_argument("-s", "--sensors",
        type=str, choices=device_names, nargs="+",
        help="Specific sensors to connect to.")
    parser.add_argument("-t", "--timeout",
        type=float, default=10,
        help="Timeout (seconds) to scan for BLE sensor devices.")
    parser.add_argument("-a", "--all",
        action="store_true", default=False,
        help="Force connection to all indicated sensors.")
    parser.add_argument("-d", "--debug",
        action="store_true", default=False,
        help="Enable debug logging.")
    args = parser.parse_args()

    # Configure logger.
    logging.basicConfig(
        handlers=[
            logging.FileHandler("output.log"),
            logging.StreamHandler()
        ],
        datefmt='%H:%M:%S',
        format='{name:.<15} {asctime}: [{levelname}] {message}',
        style='{', level=logging.DEBUG if args.debug else logging.INFO)
    log = getLogger("main")
    getLogger("asyncio").setLevel(logging.CRITICAL)

    max_connections = 4
    if args.sensors:
        device_names = args.sensors
        max_connections = len(device_names)
    elif args.num_sensors:
        max_connections = args.num_sensors

    device_addrs = [NameToAddressMap[name] for name in device_names]

    log.info(f"Start time: {datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()}")
    log.info(f"Max connections: {max_connections}")
    log.info(f"  Force all: {args.all}")
    log.info(f"Device whitelist: {device_names}")
    log.info(f"Scan timeout: {args.timeout}")

    # Config.
    qin = Queue()
    qout = Queue()
    pq = Queue()

    csvwriter = csvw.CSVWriter(qin)

    # Find sensors.
    log.info("Scanning for Posey sensors...")
    ble = BLERadio()
    all_adv = set()
    advertisements = {}
    for adv in ble.start_scan(Advertisement, timeout=args.timeout):
        if adv.address in all_adv:
            continue
        all_adv.add(adv.address)
        if (adv.complete_name == 'Posey Sensor') and (adv.address not in advertisements):
            name = AddressToNameMap[adv.address.string] if adv.address.string in AddressToNameMap else 'Unknown'
            log.info(f"Found Posey {name} (Address: {adv.address.string})")
            if name in device_names:
                advertisements[name] = adv
                if len(advertisements) == max_connections:
                    log.info(f"Found {max_connections} sensors, ending scan.")
                    ble.stop_scan()
                    break
            else:
                log.info(f" - Device not in whitelist; skipping.")

    if args.all and (len(advertisements) != max_connections):
        log.critical(f"Connected to {len(advertisements)} but require {max_connections}. Bailing.")
        raise RuntimeError("Unable to find required devices.")

    log.info(f"Connecting to {len(advertisements)} sensors.")
    sensors = []
    for name, adv in advertisements.items():
        sensor = PoseySensor(name, ble, adv, qout, qin, pq)
        log.info(f"Connecting to device {sensor}")
        if sensor.connect():
            log.info(" - Connected.")
            sensors.append(sensor)
        else:
            log.error(" - Failed to connect to BLE device.")

    try:
        csvwriter.start()

        while True:
            # Loop through sensors and try to collect data.
            for sensor in sensors:
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

    log.info("Disconnecting sensors...")
    for sensor in sensors:
        sensor.disconnect()
        sensor.hil.close()
    log.info("Stopping CSV writer...")
    csvwriter.stop()

if __name__ == "__main__":
    main()
