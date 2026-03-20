# Welch Allyn SureBP Python Client

Python client for Welch Allyn SureBP BLE home blood pressure meters. Uses the Bleak Python BLE
library.

These devices require a Welch Allyn Android app which is no longer practically installable, as it
has not been updated to support modern 64 bit Android (as of June 2025). (Update: There appears to
be a new official Android app as of March 2026).

## Devices

Tested with the Welch Allyn H-BP100-SBP SureBP device.

These devices appear to use a BLE chipset and protocol from Transtek. The bulk of the code handling
this protocol is in the `surebp` package in this project.

## Installation

    git clone https://github.com/casebeer/welch-allyn-surebp-python
    cd welch-allyn-surebp-python
    python3 -m venv venv
    venv/bin/pip install -e .

## Usage

You'll need:

1. A Welch Allyn SureBP device, like the H-BP100-SBP.

*Note that using this script will download all blood pressure readings still on the device. Once a
blood pressure reading has been downloaded by any app, it is erased from the device and will NOT be
availalble for reading by the official Welch Allyn app.*

Use the `wa.py` script to test connection to your blood pressure monitor.

First, start the script:

    venv/bin/python wa.py

Now, use the blood pressure meter to take a reading. Once the reading completes, the blood pressure
device will broadcast via BLE.

The `wa.py` script should receive this broadcast, connect to the device, and download and print out
all blood pressure readings on the device. Note that the device will only send each BP reading once,
to one client, so after reading, there will be no BP data stored on the device.

If you've used the BP device to take multiple readings without downloading them, the script should
read and delete all of them from the device. If there are no stored readings, the script should get
only one (the current) reading.

You can also specify an exact device BLE address (or, on MacOS, a device address UUID), and the
script will attempt to connect to that device rather than wait to receive an advertisement:

    venv/bin/python wa.py <BLE address or UUID>

## Notes

- During development, delays from printing to `stdout` caused sufficient BLE timing problems to
  prevent receiving more than one BP reading at a time. The Transtek BLE protocol does not give the
  client any means to control the sending of data and does not retry, so a missed incoming BLE
  indication will terminate the connection and prevent reading any futher data.

  Because of these timing issues, while the client library offers an async generator to receive BP
  data in realtime, it's probably best to not read that generator until after all BP data has been
  read and the device has already disconnected. This will minimize the risk that your code could
  cause delays leading to missed BLE indications.

  You can delay until after the device has disconnected by awaiting the `join()` method before
  reading data:

      await controller.join()
      async for data in controller.bpData():
          ...

## Future work

- Reduce blocking calls (e.g. `pprint.pformat()`, `logger.debug()`, etc.) in the BLE client to
  minimise risk of missed BLE data.
- Move BLE client into a separate thread to decouple from end-user blocking calls (like printing
  while reading from the `TranstekController.bpData()` async generator.
