Installation
============

Prerequisits
------------

Prior to installing this package you need to build the python module included in the `posey-pc <https://github.com/SML-Posey/posey-pc>`_ and install it into your Python environment.

Installation
------------

To install the package, run the following command from the root directory of the package:

.. code-block:: bash

    python setup.py install

That's it. You should now be able to import the package in your Python environment:

.. code-block:: python

    import poseyctrl

And you should see a few tools available in your path, e.g.,:

.. code-block:: bash

    posey-sniffer -h
    usage: posey-sniffer [-h] [-t TIMEOUT] [-r MIN_RSSI] [-d]

    Scan for Posey sensors.

    optional arguments:
    -h, --help            show this help message and exit
    -t TIMEOUT, --timeout TIMEOUT
                            Timeout (seconds) to scan for BLE sensor devices.
    -r MIN_RSSI, --min-rssi MIN_RSSI
                            Minimum device RSSI.
    -d, --debug           Enable debug logging.