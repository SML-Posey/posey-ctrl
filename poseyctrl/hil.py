from inspect import trace
import traceback
import time
import datetime as dt
import logging
import math
import os

from typing import Optional
from multiprocess import Queue
import numpy as np

import pyposey as pyp


class PoseyHILStats:
    def __init__(self, log, delay=3):
        self.log = log
        self.start_time = time.time()
        self.last_update = self.start_time
        self.last_timestamp = 0
        self.last_Vbatt = 0
        self.ble_throughput = 0
        self.delay = delay

        self.bytes = 0
        self.task = 0
        self.datasummary = 0
        self.imu = 0
        self.ble = 0

    def add_task(self, timestamp, bytes, Vbatt, ble_throughput=0):
        self.bytes += bytes
        self.task += 1
        self.last_timestamp = timestamp
        self.last_Vbatt = Vbatt
        self.ble_throughput = ble_throughput

    def add_datasummary(self):
        self.bytes += 15 + 3
        self.task += 1

    def add_imu(self):
        self.bytes += 27 + 3
        self.imu += 1

    def add_ble(self):
        self.bytes += 12 + 3
        self.ble += 1

    def stats(self, name, N, dt, postfix="Hz"):
        Hz = N / dt
        return f"{name}: {Hz:5.1f}{postfix}"

    def runtime(self):
        rt = time.time() - self.start_time
        return f"{str(dt.timedelta(seconds=math.floor(rt)))} / MCU {str(dt.timedelta(seconds=math.floor(self.last_timestamp*1e-6)))}"

    def log_stats(self):
        now = time.time()
        dt = now - self.last_update
        if dt >= self.delay:
            batt_pct = (self.last_Vbatt - 3.3) / (4.2 - 3.3) * 100.0
            self.log.info(
                f'RT: [{self.runtime()}] Batt: {self.last_Vbatt:.2f}V ({batt_pct:.0f}%) BLE: {self.ble_throughput} Rates: [{self.stats("T", self.task, dt)} {self.stats("I", self.imu, dt)} {self.stats("B", self.ble, dt, postfix="dps")} {self.stats("BW", self.bytes/1024.0, dt, postfix="KBps")}]'
            )

            self.bytes = 0
            self.task = 0
            self.datasummary = 0
            self.imu = 0
            self.ble = 0
            self.last_update = now


class PoseyHILReceiveMessages:
    def __init__(self):
        self.taskwaist = pyp.tasks.TaskWaistTelemetryMessage()
        self.taskwatch = pyp.tasks.TaskWatchTelemetryMessage()

        self.command = pyp.control.CommandMessage()
        self.datasummary = pyp.control.DataSummaryMessage()

        self.imu = pyp.platform.sensors.IMUMessage()
        self.ble = pyp.platform.sensors.BLEMessage()

    def register_listeners(self, ml: pyp.platform.io.MessageListener):
        ml.add_listener(self.taskwatch)
        ml.add_listener(self.taskwaist)

        ml.add_listener(self.command)
        ml.add_listener(self.datasummary)

        ml.add_listener(self.imu)
        ml.add_listener(self.ble)


class PoseyHIL:
    def __init__(
        self,
        name: str,
        qin: Queue,
        qout: Queue,
        pq: Queue,
        adv,
        connection,
        service,
        output_raw: Optional[str] = None,
    ):
        self.log = logging.getLogger(f"posey.{name}")
        self.stats = PoseyHILStats(self.log)
        self.last_ping = 0

        self.adv = adv
        self.uart_conn = connection
        self.uart_service = service

        self.qin = qin
        self.qout = qout
        self.pq = pq

        self.name = name
        if output_raw is not None:
            self.output_raw = output_raw

            self.raw_serial_in_fn = f"{self.output_raw}.in.bin"
            self.raw_serial_in = open(self.raw_serial_in_fn, "wb")

            self.raw_serial_out_fn = f"{self.output_raw}.out.bin"
            self.raw_serial_out = open(self.raw_serial_out_fn, "wb")
        else:
            self.raw_serial_in = None
            self.raw_serial_out = None

        self.messages = PoseyHILReceiveMessages()
        self.ml = pyp.platform.io.MessageListener()
        self.messages.register_listeners(self.ml)

    def flush(self):
        pass

    @staticmethod
    def Vbatt_counts_to_V(counts):
        return counts / 255.0 * 4.2 + 3.2

    def process_message(self, time: dt.datetime, mid: int):
        sig = None
        data = None
        send_to_pq = False
        if mid == pyp.tasks.TaskWaistTelemetry.message_id:
            sig = "taskwaist"
            if self.messages.taskwaist.valid_checksum:
                Vbatt = self.Vbatt_counts_to_V(self.messages.taskwaist.message.Vbatt)
                self.stats.add_task(
                    self.messages.taskwaist.message.t_start,
                    15 + 3,
                    Vbatt,
                    self.messages.taskwaist.message.ble_throughput,
                )
                self.messages.taskwaist.deserialize()
                data = {
                    "sensor": self.name,
                    "t_start": self.messages.taskwaist.message.t_start,
                    "t_end": self.messages.taskwaist.message.t_end,
                    "invalid_checksum": self.messages.taskwaist.message.invalid_checksum,
                    "missed_deadline": self.messages.taskwaist.message.missed_deadline,
                    "Vbatt": Vbatt,
                    "ble_throughput": self.messages.taskwaist.message.ble_throughput,
                }
            else:
                self.log.error("Invalid TaskWaist checkum.")

        elif mid == pyp.tasks.TaskWatchTelemetry.message_id:
            sig = "taskwatch"
            if self.messages.taskwatch.valid_checksum:
                Vbatt = self.Vbatt_counts_to_V(self.messages.taskwatch.message.Vbatt)
                self.stats.add_task(
                    self.messages.taskwatch.message.t_start,
                    12 + 3,
                    Vbatt,
                )
                self.messages.taskwatch.deserialize()
                data = {
                    "sensor": self.name,
                    "t_start": self.messages.taskwatch.message.t_start,
                    "t_end": self.messages.taskwatch.message.t_end,
                    "invalid_checksum": self.messages.taskwatch.message.invalid_checksum,
                    "missed_deadline": self.messages.taskwatch.message.missed_deadline,
                    "Vbatt": Vbatt,
                }
            else:
                self.log.error("Invalid TaskWatch checkum.")

        elif mid == pyp.control.Command.message_id:
            # If we get a command message, it must be an acknowledgement. Store
            # in a queue to be retrieved later.
            send_to_pq = True
            sig = "command"
            if self.messages.command.valid_checksum:
                self.messages.command.deserialize()
                data = {
                    "sensor": self.name,
                    "command": self.messages.command.message.command,
                    "payload": self.messages.command.message.payload,
                    "ack": self.messages.command.message.ack,
                }
            else:
                self.log.error("Invalid Command checkum.")

        elif mid == pyp.control.DataSummary.message_id:
            # If we get a data summary message, we're going to want to use it
            # to provide information on our download.
            send_to_pq = True
            sig = "datasummary"
            if self.messages.datasummary.valid_checksum:
                self.messages.datasummary.deserialize()
                data = {
                    "sensor": self.name,
                    "datetime": self.messages.datasummary.message.datetime.tobytes().decode(
                        "UTF-8"
                    ),
                    "start_ms": self.messages.datasummary.message.start_ms,
                    "end_ms": self.messages.datasummary.message.end_ms,
                    "bytes": self.messages.datasummary.message.bytes,
                }
            else:
                self.log.error("Invalid DataSummary checkum.")

        elif mid == pyp.platform.sensors.IMUData.message_id:
            sig = "imu"
            if self.messages.imu.valid_checksum:
                self.stats.add_imu()
                self.messages.imu.deserialize()
                data = {
                    "sensor": self.name,
                    "time": self.messages.imu.message.time,
                    "Ax": self.messages.imu.message.Ax,
                    "Ay": self.messages.imu.message.Ay,
                    "Az": self.messages.imu.message.Az,
                    "Qi": self.messages.imu.message.Qi,
                    "Qj": self.messages.imu.message.Qj,
                    "Qk": self.messages.imu.message.Qk,
                    "Qr": self.messages.imu.message.Qr,
                }
            else:
                self.log.error("Invalid IMU checkum.")

        elif mid == pyp.platform.sensors.BLEData.message_id:
            sig = "ble"
            if self.messages.ble.valid_checksum:
                self.stats.add_ble()
                self.messages.ble.deserialize()
                data = {
                    "sensor": self.name,
                    "time": self.messages.ble.message.time,
                    "uuid": "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}".format(
                        *self.messages.ble.message.uuid[::-1]
                    ),
                    "major": self.messages.ble.message.major,
                    "minor": self.messages.ble.message.minor,
                    "power": self.messages.ble.message.power,
                    "rssi": self.messages.ble.message.rssi,
                }
            else:
                self.log.error("Invalid BLE checkum.")
        else:
            self.log.error(f"Invalid message ID: {mid}")

        if sig is not None:
            self.qout.put((sig, time, data))
            if send_to_pq:
                self.pq.put((sig, time, data))

    def send(self, cmd):
        try:
            if hasattr(cmd, "buffer"):
                tx = cmd.buffer.buffer.tobytes()
            else:
                tx = cmd

            if self.raw_serial_out is not None:
                self.raw_serial_out.write(tx)

            if self.uart_conn.connected:
                self.uart_service.write(tx)

            return True
        except:
            self.log.error("Sending failed")
            self.log.error(traceback.format_exc())
            return False

    def close(self):
        if self.raw_serial_in is not None:
            self.raw_serial_in.close()
            self.raw_serial_in = None
            if os.path.getsize(self.raw_serial_in_fn) == 0:
                self.log.warning(
                    f"Input file {self.raw_serial_in_fn} is empty, removing..."
                )
                os.remove(self.raw_serial_in_fn)
        if self.raw_serial_out is not None:
            self.raw_serial_out.close()
            self.raw_serial_out = None
            if os.path.getsize(self.raw_serial_out_fn) == 0:
                self.log.warning(
                    f"Output file {self.raw_serial_out_fn} is empty, removing..."
                )
                os.remove(self.raw_serial_out_fn)

    def read_uart(self, size: int = -1):
        if size < 0:
            size = self.uart_service.in_waiting
        data = self.uart_service.read(size)
        if data is not None:
            data = bytes(data)
        return data

    def process_uart(self, decode_messages=True):
        to_read = 0
        data = None
        if self.uart_conn and self.uart_conn.connected:
            if decode_messages:
                to_read = min(self.uart_service.in_waiting, self.ml.free)
            else:
                to_read = self.uart_service.in_waiting

            if to_read > 0:
                data = self.read_uart(to_read)
                if (data is not None) and (self.raw_serial_in is not None):
                    self.raw_serial_in.write(data)

            if decode_messages:
                if data is not None:
                    self.ml.write(data)
                mid = self.ml.process_next()
                if mid >= 0:
                    self.process_message(dt.datetime.now(), mid)

            # This is unnecessary, but just in case we want it sometime in the future.
            # self.keep_alive()

        return to_read

    def decode_buffer(self, buffer):
        try:
            N = len(buffer)
            bytes_left = N
            while bytes_left > 0:
                to_read = min(bytes_left, self.ml.free)
                if to_read > 0:
                    si = N - bytes_left
                    ei = si + to_read
                    data = bytes(buffer[si:ei])
                    self.ml.write(data)
                    bytes_left -= to_read

                while True:
                    mid = self.ml.process_next()
                    if mid >= 0:
                        self.process_message(dt.datetime.now(), mid)
                    else:
                        break
            self.log.info("Dumping to CSV, this may take a while...")
            iter = 0
            while not self.qin.empty():
                iter += 1
                if (iter % 30) == 0:
                    self.log.info(" - Still waiting for queue to empty...")
                time.sleep(1)
        except KeyboardInterrupt:
            self.log.info("Keyboard interrupt, stopping...")

    def keep_alive(self):
        if self.uart_conn and self.uart_conn.connected:
            t = time.time()
            if (t - self.last_ping) > 1:
                # self.log.info("Sending ping.")
                self.last_ping = t
                self.send(bytes("Stayin alive!\n", "utf-8"))
