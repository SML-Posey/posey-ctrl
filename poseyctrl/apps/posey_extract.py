from logging import getLogger

import os
import time
import argparse
import logging
import traceback
from multiprocess import Queue
import datetime
import numpy as np
from hexdump import hexdump
from dateutil.parser import parse
import pandas as pd

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement

import pyposey as pyp
from pyposey import MessageAck
from pyposey.control import CommandType, CommandMessage


def posey_extract():
    # Process arguments.
    parser = argparse.ArgumentParser(
        "posey-extract",
        description="Extract and decode data downloaded from a Posey hub.",
    )
    parser.add_argument("filename", type=str, help="File (*.npz) to extract.")
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging.",
    )
    parser.add_argument(
        "-l", "--log", action="store_true", default=False, help="Output log to file."
    )
    parser.add_argument(
        "-p",
        "--prefix",
        action="store_true",
        default=False,
        help="Use long prefix for bin files.",
    )
    args = parser.parse_args()

    # Configure logger.
    handlers = [logging.StreamHandler()]
    dtnow = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nowstamp = f"{dtnow}-posey-extract"
    if args.log:
        handlers.append(logging.FileHandler(f"{nowstamp}.log"))
    logging.basicConfig(
        handlers=handlers,
        datefmt="%H:%M:%S",
        format="{name:.<15} {asctime}: [{levelname}] {message}",
        style="{",
        level=logging.DEBUG if args.debug else logging.INFO,
    )
    log = getLogger("main")
    getLogger("asyncio").setLevel(logging.CRITICAL)

    prefix = (
        (os.path.basename(args.filename).replace(".npz", "") + "-")
        if args.prefix
        else ""
    )

    # Load the data.
    f = np.load(args.filename, allow_pickle=True)
    summary = f["summary"].item()
    data = f["data"]
    datab = data.tobytes()
    f.close()

    # Extract the collection summary.
    sensor = summary["sensor"]
    dt = parse(summary["datetime"][:19])
    data_len = summary["bytes"]
    start_ms = summary["start_ms"]
    data_dt = (summary["end_ms"] - summary["start_ms"]) * 1.0e-3
    rate = data_len / data_dt

    log.info(f"Sensor: {sensor}")
    log.info(f"Date  : {dt}")
    log.info(f"Duration: {data_dt:.2f} s ({data_dt/60:.2f} m)")
    log.info(f"Data  : {data_len} B ({data_len/1024.0:.2f} KB)")
    if data_len != len(data):
        log.warning(f" -> Warning: {data_len} != {len(data)}")
    log.info(f"Rate  : {rate/1024.0:.2f} KB/s")

    log.info(
        "Extracting data collected on %s from sensor %s",
        dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        sensor,
    )
    log.info("%.2f minutes of data, %d bytes", data_dt / 60.0, data_len)

    # Extract all the blocks.
    def mac2str(mac):
        return "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(*mac)

    def extract_fbm(fbm, print_fbm=True):
        time = fbm.message.time - start_ms
        slot = fbm.message.slot
        mac = mac2str(fbm.message.mac)
        rssi = fbm.message.rssi
        block_bytes = fbm.message.block_bytes

        if print_fbm:
            log.debug(
                f"Block of {block_bytes} bytes from MAC {mac}, slot {slot} at time {time}, RSSI {rssi}"
            )

        return dict(slot=slot, time=time, mac=mac, rssi=rssi, block_bytes=block_bytes)

    block_summaries = []
    blocks = {}

    fbm = pyp.platform.sensors.FlashBlockMessage()
    di = 0
    skipped = 0
    fbm_bytes = 0
    data_bytes = 0
    while di < data_len:
        fbm.buffer.write(data[di : di + 18])
        fbm.deserialize()
        if (not fbm.valid_checksum) or (datab[di : di + 2] != b"\xca\xfe"):
            next_sync = datab.find(b"\xCA\xFE", di + 1)
            if next_sync < 0:
                next_sync = data_len
            skip = next_sync - di
            skipped += skip
            log.debug(f"Invalid FBM checksum! Skipping {skip} bytes!")
            skip += 20
            if skip > 100:
                skip = 100
            log.debug(hexdump(data[di : di + skip], result="return"))
            di = next_sync
            continue

        block_summary = extract_fbm(fbm, print_fbm=False)
        fbm_bytes += 18
        data_bytes += block_summary["block_bytes"]
        block_si = di + 18
        block_ei = block_si + block_summary["block_bytes"]
        block = data[block_si:block_ei]
        block_summaries.append(block_summary)

        slot = block_summary["slot"]
        if slot not in blocks:
            log.debug("-----------")
            log.debug(hexdump(data[di : di + 18], result="return"))
            log.debug(f"Added new slot: {slot} {block_summary['mac']}")
            extract_fbm(fbm)
            log.debug(hexdump(block, result="return"))
            log.debug("-----------")

            blocks[slot] = []
        blocks[slot].append(block)
        di = block_ei

    log.info(
        f"Total bytes  : {data_len:7} ({data_len/1024.0:7.2f} KB) {data_len*100.0/data_len:6.2f}%"
    )
    log.info(
        f"Skipped bytes: {skipped:7} ({skipped/1024.0:7.2f} KB) {skipped*100.0/data_len:6.2f}%"
    )
    log.info(
        f"FBM bytes    : {fbm_bytes:7} ({fbm_bytes/1024.0:7.2f} KB) {fbm_bytes*100.0/data_len:6.2f}%"
    )
    log.info(
        f"Data bytes   : {data_bytes:7} ({data_bytes/1024.0:7.2f} KB) {data_bytes*100.0/data_len:6.2f}%"
    )

    flash_data = {}
    for slot, slot_blocks in blocks.items():
        flash_data[slot] = np.concatenate(slot_blocks)
        log.info(
            f"Slot {slot:3d}: Concatenated {len(slot_blocks):8d} blocks - {len(flash_data[slot]):8d} B / {len(flash_data[slot])/1024.0:8.2f} KB ({len(flash_data[slot])/1024.0/data_dt:5.2f} KB/s)"
        )

    # Write binary files.
    for slot, data in flash_data.items():
        log.info(f"Writing binary data to {prefix}{slot}.bin")
        with open(f"{prefix}{slot}.bin", "wb") as f:
            f.write(flash_data[slot].tobytes())

    # Write RSSI.
    log.info(f"Writing RSSI data to {prefix}rssi.csv")
    fbdf = pd.DataFrame.from_dict(block_summaries)
    fbdf.time *= 1.0e-3
    fbdf.to_csv(f"{prefix}rssi.csv", index=False)
