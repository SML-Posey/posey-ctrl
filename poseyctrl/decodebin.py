import os
import datetime as dt
import time

from multiprocess import Queue

from poseyctrl import csvw
from poseyctrl import hil

import argparse

def decodebin():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, help="Input bin.")
    parser.add_argument("output", type=str, default=".", nargs="?",
        help="Output directory.")
    parser.add_argument("-p", "--prefix", type=str, default=None,
        help="Output prefix.")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file does not exist! -> {args.input}")
    if not os.path.isdir(args.output):
        print(f"Error: output directory does not exist! -> {args.output}")
    if args.prefix is None:
        args.prefix = os.path.basename(args.input) \
            .replace(".raw", "") \
            .replace(".in", "") \
            .replace(".out", "") \
            .replace(".bin", "")

    print(f"Processing {args.input} -> {args.output}/{args.prefix}.*")
    inp = open(args.input, 'rb').read()
    os.chdir(args.output)

    qin = Queue()
    qout = Queue()
    pq = Queue()

    csvwriter = csvw.CSVWriter(qin, prefix=f"{args.prefix}.")
    sensor = hil.PoseyHIL(
        args.prefix, qout, qin, pq,
        None, None, None, output_raw = False)

    try:
        print(f"Reading {args.input}...")
        csvwriter.start()
        N = len(inp)
        bytes_left = N
        rows = {1: 0, 2: 0, 200: 0}
        while bytes_left > 0:
            to_read = min(bytes_left, sensor.ml.free)
            if to_read > 0:
                si = N - bytes_left
                ei = si + to_read
                data = bytes(inp[si:ei])
                sensor.ml.write(data)
                bytes_left -= to_read

            while True:
                mid = sensor.ml.process_next()
                if mid >= 0:
                    rows[mid] += 1
                    sensor.process_message(dt.datetime.now(), mid)
                else:
                    break
        print("Dumping to CSV, this may take a while...")
        iter = 0
        while not qin.empty():
            iter += 1
            if (iter % 30) == 0:
                print(" - Still waiting for queue to empty...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt, stopping...")
    print("Done.")

if __name__ == "__main__":
    decodebin()
