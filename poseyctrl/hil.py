from inspect import trace
import traceback
import time
import datetime as dt
import logging

from typing import Optional
from multiprocess import Queue, Process
import numpy as np

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement
#from adafruit_ble.services.nordic import UARTService
from poseyctrl.patch.nordic import UARTService


import pyposey as pyp


class PoseyHILStats:
    def __init__(self, log, delay=3):
        self.log = log
        self.last_update = time.time()
        self.delay = delay

        self.bytes = 0
        self.taskmain = 0
        self.imu = 0
        self.ble = 0

    def add_taskmain(self):
        self.bytes += 15
        self.taskmain += 1

    def add_imu(self):
        self.bytes += 77
        self.imu += 1

    def add_ble(self):
        self.bytes += 12
        self.ble += 1

    def stats(self, name, N, dt, postfix='Hz'):
        Hz = N/dt
        return f'[{name}: {Hz:5.1f}{postfix}]'

    def log_stats(self):
        now = time.time()
        dt = now - self.last_update
        if dt >= self.delay:
            self.log.info(f'{self.stats("Main", self.taskmain, dt)} {self.stats("IMU", self.imu, dt)} {self.stats("BLE", self.ble, dt)} {self.stats("Throughput:", self.bytes, dt, postfix="bps")}')

            self.bytes = 0
            self.taskmain = 0
            self.imu = 0
            self.ble = 0
            self.last_update = now


class PoseyHILReceiveMessages:
    def __init__(self):
        self.taskmain = pyp.tasks.TaskMainTelemetryMessage()

        # self.command = pyp.control.CommandMessage()

        self.imu = pyp.platform.sensors.IMUMessage()
        self.ble = pyp.platform.sensors.BLEMessage()

    def register_listeners(self, ml: pyp.platform.io.MessageListener):
        ml.add_listener(self.taskmain)

        # ml.add_listener(self.command)

        ml.add_listener(self.imu)
        ml.add_listener(self.ble)

class PoseyHIL:
    def __init__(self,
            name: str,
            qin: Queue, qout: Queue, pq: Queue,
            adv, connection, service):
        self.log = logging.getLogger(f'posey.{name}')
        self.stats = PoseyHILStats(self.log)

        self.adv = adv
        self.uart_conn = connection
        self.uart_service = service

        self.qin = qin
        self.qout = qout
        self.pq = pq

        self.name = name

        self.raw_serial_in = open(f'{self.name}.raw.in.bin', 'wb')
        self.raw_serial_out = open(f'{self.name}.raw.out.bin', 'wb')

        self.messages = PoseyHILReceiveMessages()
        self.ml = pyp.platform.io.MessageListener()
        self.messages.register_listeners(self.ml)

    def flush(self):
        pass

    def process_message(self, time: dt.datetime, mid: int):
        sig = None
        data = None
        send_to_pq = False
        if mid == pyp.tasks.TaskMainTelemetry.message_id:
            sig = 'taskmain'
            if self.messages.taskmain.valid_checksum:
                self.stats.add_taskmain()
                self.messages.taskmain.deserialize()
                data = {
                    'sensor': self.name,
                    'counter': self.messages.taskmain.message.counter,
                    't_start': self.messages.taskmain.message.t_start,
                    't_end': self.messages.taskmain.message.t_end,
                    'invalid_checksum': self.messages.taskmain.message.invalid_checksum,
                    'missed_deadline': self.messages.taskmain.message.missed_deadline}
            else:
                self.log.error('Invalid TaskMain checkum.')
        # elif mid == pyp.control.Command.message_id:
        #     # If we get a command message, it must be an acknowledgement. Store
        #     # in a queue to be retrieved later.
        #     send_to_pq = True
        #     sig = 'command'
        #     if self.messages.command.valid_checksum:
        #         self.messages.command.deserialize()
        #         data = {
        #             'sensor': self.name,
        #             'command': self.messages.command.message.command,
        #             'arg1': self.messages.command.message.arg1,
        #             'arg2': self.messages.command.message.arg2,
        #             'arg3': self.messages.command.message.arg3,
        #             'ack': self.messages.command.message.ack}
        #     else:
        #         self.log.error('Invalid Command checkum.')
        elif mid == pyp.platform.sensors.IMUData.message_id:
            sig = 'imu'
            if self.messages.imu.valid_checksum:
                self.stats.add_imu()
                self.messages.imu.deserialize()
                data = {
                    'sensor': self.name,
                    'time': self.messages.imu.message.time,
                    'An': self.messages.imu.message.An,
                    # 'Gn': self.messages.imu.message.Gn,
                    # 'Mn': self.messages.imu.message.Mn,
                    'Qn': self.messages.imu.message.Qn,
                    'Ax': self.messages.imu.message.Ax,
                    'Ay': self.messages.imu.message.Ay,
                    'Az': self.messages.imu.message.Az,
                    # 'Gx': self.messages.imu.message.Gx,
                    # 'Gy': self.messages.imu.message.Gy,
                    # 'Gz': self.messages.imu.message.Gz,
                    # 'Mx': self.messages.imu.message.Mx,
                    # 'My': self.messages.imu.message.My,
                    # 'Mz': self.messages.imu.message.Mz,
                    'Qi': self.messages.imu.message.Qi,
                    'Qj': self.messages.imu.message.Qj,
                    'Qk': self.messages.imu.message.Qk,
                    'Qr': self.messages.imu.message.Qr,
                    'Qacc': self.messages.imu.message.Qacc}
            else:
                self.log.error('Invalid IMU checkum.')

        elif mid == pyp.platform.sensors.BLEData.message_id:
            sig = 'ble'
            if self.messages.ble.valid_checksum:
                self.stats.add_ble()
                self.messages.ble.deserialize()
                data = {
                    'sensor': self.name,
                    'time': self.messages.ble.message.time,
                    'addr': '{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}'.format(
                        *self.messages.ble.message.addr[::-1]),
                    'rssi': self.messages.ble.message.rssi}
            else:
                self.log.error('Invalid BLE checkum.')
        else:
            self.log.error(f'Invalid message ID: {mid}')

        if sig is not None:
            self.qout.put((sig, time, data))
            if send_to_pq:
                self.pq.put((sig, time, data))

    def send(self, cmd):
        try:
            tx = cmd

            if self.raw_serial_out is not None:
                self.raw_serial_out.write(tx)

            if self.uart_conn.connected:
                self.uart_service.write(tx)

            return True
        except:
            self.log.error('Sending failed')
            self.log.error(traceback.format_exc())
            return False

    def close(self):
        if self.raw_serial_in is not None:
            self.raw_serial_in.close()
            self.raw_serial_in = None
        if self.raw_serial_out is not None:
            self.raw_serial_out.close()
            self.raw_serial_out = None

    def process_uart(self):
        if self.uart_conn and self.uart_conn.connected:
            to_read = min(self.uart_service.in_waiting, self.ml.free)
            if to_read > 0:
                data = bytes(self.uart_service.read(to_read))
                self.ml.write(data)
                if self.raw_serial_in is not None:
                    self.raw_serial_in.write(data)

            mid = self.ml.process_next()
            if mid >= 0:
                self.process_message(dt.datetime.now(), mid)

