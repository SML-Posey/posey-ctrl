from logging import getLogger

import os
import time
import argparse
import logging
import traceback
from multiprocess import Queue
import datetime as dt
import numpy as np
from dateutil.parser import parse

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement

from poseyctrl import csvw, hil

import pyposey as pyp
from pyposey import MessageAck
from pyposey.control import CommandType, CommandMessage


def posey_extract():

    # Process arguments.
    parser = argparse.ArgumentParser(
        "posey-extract",
        description="Extract and decode data downloaded from a Posey hub.")
    parser.add_argument("filename",
        type=str, help="File (*.npz) to extract.")
    parser.add_argument("-d", "--debug",
        action="store_true", default=False,
        help="Enable debug logging.")
    parser.add_argument("-l", "--log",
        action="store_true", default=False,
        help="Output log to file.")
    parser.add_argument("-p", "--prefix",
        action="store_true", default=False,
        help="Use long prefix for CSV files.")
    args = parser.parse_args()

    # Configure logger.
    handlers = [logging.StreamHandler()]
    dtnow = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    nowstamp = f"{dtnow}-posey-extract"
    if args.log:
        handlers.append(logging.FileHandler(f"{nowstamp}.log"))
    logging.basicConfig(
        handlers=handlers,
        datefmt='%H:%M:%S',
        format='{name:.<15} {asctime}: [{levelname}] {message}',
        style='{', level=logging.DEBUG if args.debug else logging.INFO)
    log = getLogger("main")
    getLogger("asyncio").setLevel(logging.CRITICAL)

    # Initialize CSV writer.
    qin = Queue()
    qout = Queue()
    pq = Queue()
    prefix = (os.path.basename(args.filename).replace(".npz", "") + "-") if args.prefix else ""
    csvwriter = csvw.CSVWriter(qin, prefix=f"{prefix}.")
    csvwriter.start()

    # Load the data.
    f = np.load(args.filename, allow_pickle=True)
    summary = f['summary'].item()
    data = f['data'].tobytes()
    flash_data_buffers = {}

    # Extract the collection summary.
    sensor = summary['sensor']
    start_time = parse(summary['datetime'])
    mcu_ts = summary['start_ms']
    mcu_te = summary['end_ms']
    duration = (mcu_te - mcu_ts)*1.0e-3
    data_size = summary['bytes']

    log.info("Extracting data collected on %s from sensor %s",
        start_time.strftime('%Y-%m-%d %H:%M:%S %Z'), sensor)
    log.info("%.2f minutes of data, %d bytes", duration/60.0, data_size)

    if data_size != len(data):
        log.warning("Data size mismatch: %d != %d", data_size, len(data))
        data_size = len(data)
    
    # Decode the data. We need to loop through looking for FlashBlock messages.
    # For each FlashBlock, we'll then a chunk of data indicated in the 
    # FlashBlock header into a new buffer to be decoded by a second     
    # MessageListener.

    def copy_to_flash_buffer(slot, data):
        # Check which flash buffer we're using.
        if slot not in flash_data_buffers:
            flash_desc = {
                'cursor': 0,
                'buffer': np.empty(f['data'].shape, dtype=np.uint8)
            }
            flash_data_buffers[slot] = flash_desc

        cursor = flash_data_buffers[slot]['cursor']
        buffer = flash_data_buffers[slot]['buffer']
        buffer[cursor:cursor+len(data)] = data
        flash_data_buffers[slot]['cursor'] = cursor + len(data)

    # We'll do this in two passes, even though that's pretty inefficient.

    fb_listener = pyp.platform.io.MessageListener()
    fbm = pyp.platform.sensors.FlashBlockMessage()
    fb_listener.add_listener(fbm)

    # Loop through the data, looking for FlashBlock messages.
    log.info("Extracting FlashBlocks...")
    cursor = 0
    while cursor < data_size:
        # Write to FlashBlock listerner.
        to_write = 300
        if (cursor + to_write) >= data_size:
            to_write = data_size - cursor
        written = fb_listener.write(data[cursor:cursor+to_write])
        cursor += written

        # Check for FlashBlock messages.
        mid = fb_listener.process_next()
        if mid == fbm.message.message_id:
            if not fbm.valid_checksum:
                log.warning("Invalid FlashBlock checksum, skipping.")
                continue
            fbm.deserialize()
            fbm_data = {
                'time': fbm.message.time,
                'slot': fbm.message.slot,
                'rssi': fbm.message.rssi,
                'block_bytes': fbm.message.block_bytes
            }
            real_time = start_time + dt.timedelta(
                milliseconds=fbm_data['time'] - mcu_ts)
            qin.put(("flashblock", real_time, fbm_data))
            slot = fbm_data['slot']

            # Now we possibly need to take bytes out of the fb_listerner's
            # buffer and add them to the appropriate flash buffer.
            block_bytes = fbm_data['block_bytes']
            copy_size = fb_listener.used
            if copy_size > block_bytes:
                copy_size = block_bytes
            if copy_size > 0:
                copy_to_flash_buffer(slot,
                    np.frombuffer(fb_listener.read(copy_size), 'u1'))
                block_bytes -= copy_size
            if block_bytes > 0:
                copy_to_flash_buffer(slot,
                    np.frombuffer(data[cursor:cursor+block_bytes], 'u1'))
                cursor += block_bytes

    # Stop the CSV writer. We'll reopen a new CSV writer for each
    # flash buffer.
    log.info("Done extracting flash buffers, stopping CSV writer...")
    csvwriter.stop_gracefully()

    def empty_queue(q):
        while not q.empty():
            q.get()

    for slot in flash_data_buffers:
        # Reopen the CSV writer.
        empty_queue(qin)
        empty_queue(qout)
        empty_queue(pq)
        prefix = os.path.basename(args.filename).replace(".npz", "") if args.prefix else ""
        csvwriter = csvw.CSVWriter(qin, prefix=f"{prefix}slot{slot}.")
        csvwriter.start()

        # Extract the flash data.
        flash_desc = flash_data_buffers[slot]
        flash_data = flash_desc['buffer']
        flash_cursor = flash_desc['cursor']

        log.info("Extracting flash data for slot %d (%.2f MB)...", 
            slot, flash_cursor/1024.0/1024.0)
        flash_data = flash_data[:flash_cursor].tobytes()
        sensor = hil.PoseyHIL(
            prefix, qout, qin, pq,
            None, None, None, output_raw = None)
        sensor.decode_buffer(flash_data)

        # Done, close the CSV writer.
        log.info("Finished decoding, waiting for CSV writer to finish...")
        csvwriter.stop_gracefully()