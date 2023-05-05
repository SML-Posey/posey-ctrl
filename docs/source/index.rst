.. Posey Control documentation master file, created by
   sphinx-quickstart on Thu May  4 14:32:23 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Posey Control Documentation
=========================================

`posey-ctrl` is a Python package for controlling the Posey platform sensors. It includes a suite of utilities for collecting and decoding data, and sending commands to control the devices. Additionally, the modules themselves can be included in other projects to facilitate direct interfacing with the sensors in other scripts.

Sensor communication all happens over Bluetooth Low Energy links. The sensors are all based on the Nordic Semiconductor nRF52832 and nRF5340 SoCs, and use the Nordic UART Service (NUS) for communication. They are configured to advertise their presence and can be connected to by any device with a BLE radio. The devices advertise using the standard NUS UUID, and include in their name an identifier (usually a type of flower), a hardware revision, and a device role. Possible roles are hub (h), watch (v), and ring (r). Depending on the role the device has different capabilities.

Checkout the :doc:`installation` section to get the package working, then look at the :doc:`overview` to get a general idea how the components interact.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   overview
   api



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
