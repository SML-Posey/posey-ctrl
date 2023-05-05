Overview
========

This page will provide a high-level overview of the project, this package in particular, and give you a general sense of how the components work together.

What is Posey?
--------------

Posey is an open-source, open-hardware distributed wearable sensor platform for use in research or just plain fun. It is designed to be very low power while providing a much richer set of capabilities compared to commercially available wearable devices. You can learn more about the Posey project here_.

.. _here: https://github.com/SML-Posey

What does the platform look like?
---------------------------------

There are three sensor types which correspond to different roles:

- **Hub**: The hub is the central node in the network. It is responsible for collecting data from all of the sensors, storing it to onboard flash, and sending it to a computer for storage and analysis.
- **Watch**: Watches are worn on the wrists and typically act as just peripheral sensing devices. Watches typically do not include flash.
- **Ring**: The ring unit is a much smaller form factor, enabling it to sit on a finger. The size and power constraints mean there is no onboard flash, it may be desirable to operate the devices less frequently to extend runtime.

Then there is your computer which can be used to

- Directly collect data from peripheral devices (rings and watches which do not include the "hub" role);
- Collect 1Hz diagnostic data from hub devices;
- Issue commands to hub units to clear their flash, record activity, download data, etc;
- Decode data downloaded from device flash or collected directly from a peripheral sensor.

The hardware classifications also roughly correspond to particular roles each device has:

- **Hub**: Hub units include onboard flash for storing their own telemetry data along with that of any connected devices. They also detect iBeacons and log their RSSI, receive power, UUID, and major and minor IDs. If listened to, hub units will send a 1Hz diagnostic packet which includes things like missed deadlines, battery voltage, etc. Hub units are the only devices which respond to commands.
- **Watch**: Watch units are peripheral devices which send their data to a hub unit. They do not log their own telemetry or actively try to connect to other sensors. Currently IMU data is collected at 50Hz and sent over BLE if a hub unit or laptop is connected.
- **Ring**: Current iterations of the ring units use a different hardware configuration but operate the same as the watch role. For longer studies these will be changed considerably to extend the lifespan due to the greatly constrained battery capacity.

Typical experimental setup and workflow
---------------------------------------

A typical experimental workflow might look like this:

1. The devices will be disconnected from their chargers and placed on a user. 2. Each hub unit used needs to be separately sent a command to start recording data using the ``posey-cmd`` utility.
3. The devices then record data until either they are commanded to stop (again using ``\1``), or they run out of storage.
4. After the study, the devices are removed from the user and issued a command to stop recording.
5. Devices are connected to their chargers and the data is downloaded separately from each hub using the ``posey-cmd`` utility.
6. Flash data is extracted using the ``posey-extract`` utility.
7. Extracted data is decoded with the ``posey-decode`` utility.

Some helpful tips:

- The ``posey-sniffer`` utility will look for Posey device advertisements and print out the device and its RSSI. This can be useful to verify that all devices are operational.
- The ``posey-listen`` utility can connect to an individual device to either report back diagnostic data (hub devices) or to directly download sensor data (peripheral devices).
- Data will not be overwritten unless you explicitely tell the device to overwrite the data. It's also persistent in the event the battery dies.

Brief overview of the tools
---------------------------

The following utilities are included in this package:

:mod:`posey-sniffer <poseyctrl.apps.posey_sniffer>`
    This utility scans BLE advertisements for those named "Posey". It will print out the complete name along with the RSSI. This can be useful to verify that all devices are operational.

:mod:`posey-listen <poseyctrl.apps.posey_listen>`
    This utility is used to collect data from a single device. For hub devices, the only data sent is a 1Hz diagonstic packet which includes things like missed deadlines, battery voltage, etc. For peripheral devices, this actually includes all of the IMU data along with the 1Hz diagnostic telemetry. The data is dumped to a binary ``.bin`` file which can be decoded using the ``posey-decode-bin`` utility.

:mod:`posey-cmd <poseyctrl.apps.posey_cmd>`
    This utility is used to send commands to hub devices. These include device reboots, starting and stopping data logging, reading data log status and diagnostics, clearing the flash, and downloading the data, which is packaged in a pickled ``numpy`` object and saved as an ``.npz`` file.

:mod:`posey-extract <poseyctrl.apps.posey_extract>`
    This utiity extracts the flash data from a downloaded data file into a set of binary serial dumps from each sensor. These are in the same format as what you would see connected directly to a peripheral device using ``posey-listen``.

:mod:`posey-decode-bin <poseyctrl.apps.posey_decode_bin>`
    This utility extracts packets from the binary serial dumps and saves them to a set of CSV files for each packet type.
