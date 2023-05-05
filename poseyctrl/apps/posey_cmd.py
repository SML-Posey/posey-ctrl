from logging import getLogger

import time
import argparse
import logging
import traceback
from multiprocess import Queue
import queue
import bleak
import datetime as dt
from enum import Enum
import numpy as np
import json

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement

from poseyctrl.sensor import PoseySensor

from pyposey import MessageAck
from pyposey.control import CommandType, CommandMessage


def posey_cmd():
    def confirm() -> bool:
        """
        Ask user to enter Y or N (case-insensitive).

        :param return: True if the answer is Y.
        """
        answer = ""
        while answer not in ["y", "n"]:
            answer = input("Continue? [Y/N]? ").lower()
        return answer == "y"

    # Process arguments.
    parser = argparse.ArgumentParser(
        "posey-cmd", description="Send a command to a posey hub device."
    )
    parser.add_argument("sensor", type=str, help="Sensor to connect to.")
    parser.add_argument(
        "command",
        type=str,
        help="Command to issue.",
        choices=[
            "noop",
            "reboot",
            "startrecording",
            "stoprecording",
            "datasummary",
            "download",
            "flasherase",
        ],
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=10,
        help="Timeout (seconds) to scan for BLE sensor devices.",
    )
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
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="Force command without confirmation.",
    )
    args = parser.parse_args()

    # Configure logger.
    dtnow = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    nowstamp = f"{dtnow}-posey-cmd-{args.sensor}-{args.command}"
    handlers = [logging.StreamHandler()]
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

    device_name = args.sensor

    log.info(
        f"Start time: {dt.datetime.now().astimezone().replace(microsecond=0).isoformat()}"
    )
    log.info(f"Sensor: {device_name}")
    log.info(f"Scan timeout: {args.timeout}")

    # Config.
    qin = Queue()
    qout = Queue()
    pq = Queue()

    # Confirmation.
    if not args.force:
        if args.command == "flasherase":
            log.warning("This will erase all data on the device!")
            if not confirm():
                log.info("Aborting.")
                return
        elif args.command == "download":
            log.warning("This will stop recording to download data!")
            log.info("If you haven't already stopped recording, you should do")
            log.info("that instead, otherwise the end timestamp is sometimes invalid.")
            if not confirm():
                log.info("Aborting.")
                return
        elif args.command == "startrecording":
            log.warning("Starting a new recording will delete any existing data!")
            log.info("You may want to download the existing data first.")
            if not confirm():
                log.info("Aborting.")
                return
        elif args.command == "stoprecording":
            log.warning("Are you sure you want to stop recording?")
            if not confirm():
                log.info("Aborting.")
                return
        elif args.command == "reboot":
            log.warning("This will stop recording and invalidate the end timestamp!")
            log.info("If the device is recording stop it first.")
            if not confirm():
                log.info("Aborting.")
                return

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
    sensor = PoseySensor(device_name, ble, device_adv, qout, qin, pq, nowstamp)
    log.info(f"Connecting to device {sensor}")
    if sensor.connect():
        log.info(" - Connected.")
    else:
        log.error(" - Failed to connect to BLE device.")
        raise RuntimeError("Could not connect to Posey sensor!")

    def wait_for_ack(timeout=60):
        log.info("Waiting for ack...")

        # Check for ack.
        t0 = time.time()
        while True:
            try:
                (sig, _, data) = pq.get_nowait()
                if sig == "command":
                    log.info(f"Found ack: 0x{data['ack']:02x}")
                    return data
                if (timeout != None) and ((time.time() - t0) > timeout):
                    log.error("Timeout while waiting for ack!")
                    raise Exception("Timeout")
            except queue.Empty:
                pass

            sensor.hil.process_uart()
            time.sleep(0.1)

    def wait_for_datasummary(timeout=60):
        log.info("Waiting for datasummary...")

        # Check for ack.
        t0 = time.time()
        data_summary = None
        while True:
            try:
                (sig, sig_time, data) = pq.get_nowait()
                if sig == "datasummary":
                    data_summary = data
                    log.info("Got DataSummary message:")
                    log.info(json.dumps(data_summary, indent=4))
                    return data_summary
                if (timeout != None) and ((time.time() - t0) > timeout):
                    log.error("Timeout while waiting for ack!")
                    raise Exception("Timeout")
            except queue.Empty:
                pass

            sensor.hil.process_uart()
            time.sleep(0.1)

    def wait_for_download(buffer):
        bytes = len(buffer)
        log.info("Waiting for %.2f MB...", bytes / 1024.0 / 1024.0)
        bytes_left = bytes
        t0 = time.time()
        tu = t0
        bu = 0

        di = 0
        while bytes_left > 0:
            data = sensor.hil.read_uart()
            if data is not None:
                data_len = len(data)
                bytes_left -= data_len
                de = di + data_len
                if de > bytes:
                    de = bytes
                    data = data[: (de - di)]
                buffer[di:de] = np.frombuffer(data, "u1")
                di = de
            else:
                data_len = 0

            dt = 1.0 * (time.time() - tu)
            if (dt > 10) or (bytes_left <= 0):
                bytes_read = bytes - bytes_left
                log.info(
                    "Waiting for %.2f/%.2f MB (%.2f%%, %.2f KBps)",
                    bytes_left / 1024.0 / 1024.0,
                    bytes / 1024.0 / 1024.0,
                    100.0 * bytes_left / bytes,
                    (bytes_read - bu) / 1024.0 / dt,
                )
                tu = time.time()
                bu = bytes_read

            if data_len == 0:
                time.sleep(0.1)

        return bytes_read

    # Send command.
    cmd = CommandMessage()
    cmd.message.ack = MessageAck.Expected
    expected_ack = MessageAck.OK
    if args.command == "noop":
        cmd.message.command = CommandType.NoOp
    elif args.command == "reboot":
        cmd.message.command = CommandType.Reboot
    elif args.command == "startrecording":
        cmd.message.command = CommandType.StartCollecting
        cmd.message.payload = np.frombuffer(
            dt.datetime.now()
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S %Z %z")
            .encode("UTF-8"),
            dtype="u1",
        )
        expected_ack = MessageAck.Working
        log.info(
            "Data recording will start after flash erase. This may take up to a few minutes."
        )
    elif args.command == "flasherase":
        cmd.message.command = CommandType.FullFlashErase
        expected_ack = MessageAck.Working
        log.info("A full flash erase may take up to a few minutes (typical 2m30s).")
    elif args.command == "stoprecording":
        cmd.message.command = CommandType.StopCollecting
    elif (args.command == "download") or (args.command == "datasummary"):
        cmd.message.command = CommandType.GetDataSummary
    cmd.serialize()
    sensor.hil.send(cmd)
    log.info(
        f"Sent init command for {args.command}: 0x{cmd.message.command:02x} {cmd.message.command_str()}"
    )

    # Wait for ack.
    data = wait_for_ack()

    if data["ack"] != expected_ack:
        log.error(f"Bad ack returned after init: 0x{data['ack']:02x}")
    elif args.command == "flasherase":
        log.info("Waiting for acknowledgement that flash erase completed...")
        data = wait_for_ack()
        if data["ack"] != MessageAck.OK:
            log.error(f"Unexpected ack in response to flash erase: 0x{data['ack']:02x}")
    elif args.command == "startrecording":
        log.info("Waiting for acknowledgement that recording started...")
        data = wait_for_ack()
        if data["ack"] != MessageAck.OK:
            log.error(
                f"Unexpected ack in response to start recording: 0x{data['ack']:02x}"
            )
    elif args.command == "datasummary":
        data_summary = wait_for_datasummary()
        if data_summary is None:
            log.error("No DataSummary returned!")
    elif args.command == "download":
        data_summary = wait_for_datasummary()
        if data_summary is None:
            log.error("No DataSummary returned!")
        else:
            bytes = data_summary["bytes"]
            log.info(
                "Allocating download buffer for %2f MB...", bytes / 1024.0 / 1024.0
            )
            download_buffer = np.empty(bytes, "u1")

            cmd.message.command = CommandType.DownloadData
            cmd.serialize()
            sensor.hil.send(cmd)
            log.info(
                f"Sent download command: 0x{cmd.message.command:02x} {cmd.message.command_str()}"
            )

            # Wait on data summary and ack.
            data = wait_for_ack()
            if data["ack"] != MessageAck.Working:
                log.error(
                    f"Unexpected ack in response to download: 0x{data['ack']:02x}"
                )
            else:
                # Wait for download.
                bytes_read = wait_for_download(download_buffer)
                if bytes_read < bytes:
                    log.error("Only read %d of %d bytes!", bytes_read, bytes)

                fn = f"{dtnow}-{device_name.replace(' ', '')}-download.npz"
                log.info("Dumping downloaded data to file: %s", fn)
                np.savez(
                    fn, summary=data_summary, data=download_buffer, allow_pickle=True
                )
                log.info("Done!")

    # elif args.command == 'record':
    #     # Wait for keyboard interrupt, then send stop.
    #     log.info("Data is recording. Terminate recording with Ctrl+C (keyboard interrupt)")
    #     try:
    #         while True:
    #             # Connected?
    #             if not sensor.connected:
    #                 log.warning(f"Sensor {sensor.name} disconnected. Reconnecting...")
    #                 try:
    #                     sensor.connect()
    #                 except KeyboardInterrupt:
    #                     raise
    #                 except bleak.exc.BleakError as e:
    #                     msg = e.message if hasattr(e, 'message') else e
    #                     log.warning(f"Bleak error: {msg}")
    #                 except:
    #                     log.info("Exception on connect:")
    #                     traceback.print_exc()

    #                 if sensor.connected:
    #                     log.info("Reconnect successful")
    #                 else:
    #                     log.error(f"Could not reconnect to {sensor.name}!")
    #                     continue

    #             # Collect data.
    #             sensor.hil.process_uart()

    #             # If time, print statistics.
    #             sensor.hil.stats.log_stats()

    #             time.sleep(0.2)

    #     except KeyboardInterrupt:
    #         log.info("Keyboard interrupt, stopping record.")

    #     except:
    #         traceback.print_exc()

    #     # Send stop command.
    #     cmd.message.command = CommandType.StopCollecting
    #     cmd.serialize()
    #     sensor.hil.send(cmd)
    #     log.info(f'Sent stop command: 0x{cmd.message.command:02x} {cmd.message.command_str()}')

    #     # Wait for ack.
    #     data = wait_for_ack()
    #     if data['ack'] != MessageAck.OK:
    #         log.error(f"Bad ack returned from stop: 0x{data['ack']:02x}")

    log.info("Disconnecting sensor...")
    sensor.disconnect()
    sensor.hil.close()


if __name__ == "__main__":
    posey_cmd()
