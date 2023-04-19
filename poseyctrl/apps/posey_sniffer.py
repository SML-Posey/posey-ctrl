from logging import getLogger

import argparse
import logging
import datetime as dt

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement


def posey_sniffer():

    # Process arguments.
    parser = argparse.ArgumentParser(
        "posey-sniffer",
        description="Scan for Posey sensors.")
    parser.add_argument("-t", "--timeout",
        type=float, default=None,
        help="Timeout (seconds) to scan for BLE sensor devices.")
    parser.add_argument("-r", "--min-rssi",
        type=float, default=-100,
        help="Minimum device RSSI.")
    parser.add_argument("-d", "--debug",
        action="store_true", default=False,
        help="Enable debug logging.")
    args = parser.parse_args()

    # Configure logger.
    handlers = [logging.StreamHandler()]
    logging.basicConfig(
        handlers=handlers,
        datefmt='%H:%M:%S',
        format='{name:.<4} {asctime}: {message}',
        style='{', level=logging.DEBUG if args.debug else logging.INFO)
    log = getLogger("main")
    getLogger("asyncio").setLevel(logging.CRITICAL)

    # Find sensors.
    log.info(f"Scanning for Posey sensors...")
    ble = BLERadio()
    try:
        for adv in ble.start_scan(Advertisement, timeout=args.timeout, minimum_rssi=args.min_rssi):
            if adv.complete_name is None:
                continue
            cn = adv.complete_name.lower()
            if "posey" in cn:
                log.info(f"{adv.complete_name:30s} RSSI: {adv.rssi:4d} Address: {adv.address.string}")

    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, stopping.")
    
    ble.stop_scan()

if __name__ == "__main__":
    posey_sniffer()