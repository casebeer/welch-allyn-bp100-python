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

    venv/bin/python wa.py [BLE address or UUID]

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

## Transtek BLE Blood Pressure Monitor Protocol

Transtek (OEM for Welch Allyn SureBP BP100 models 1500 and 1700) BLE blood pressure monitors
exchange commands with the client via client writes to a client-to-sever characteristic and device
indications to a server-to-client characteristic subscribed to by the client.

Before sending actual blood pressure data, the device requires the client to authenticate via a
trivial challenge-response password authentication over the command characteristics.

This "password" apperars to be the last 8 hex chars of the reported device info serial number,
interpreted as four bytes. This is also the byte-wise-reversed FIRST four bytes of the MAC address.

After sending the challenge-response, the client also sets the device's time.

The BP monitor device server sends actual blood pressure data to the client via indications to a
separate blood pressure data characteristic once authentication and time setting is complete.

### Characteristics of the Transtek BP service (0x7809)

- 0x8a81 Client-to-server command characteristic (write)
- 0x8a82 Server-to-client command characteristic (indicate)
- 0x8a91 BP data characteristic (indicate)

### Command structure

Command data sent via the two command characteristics consists of one byte specifying the command
followed by between zero and four bytes of data, depending on the specific command.

Multi-byte data fields (in both commands and blood pressure data) are little endian unsigned
16-bit or 32-bit integers.

#### Known commands:

- [s2c] 0xa0 `setPassword(uint32le password)` Set long-term password for use in challenge-response
- [c2s] 0x21 `setBroadcastID(uint32le broadcastId)` Always set as 0x01 0x23 0x45 0x67
- [s2c] 0xa1 `setChallenge(uint32le challenge)` Issue random four byte authentication challenge
- [c2s] 0x20 `setChallengeResponse(uint32le response)` Compute `response = challenge ^ password`
- [c2s] 0x02 `setTime(uint32le timestampSeconds)` Set localtime in seconds since 2010-01-01
- [s2c] 0x22 `aboutToDisconnect()`
- [c2s] 0x22 `waitingForData()` Sent after receipt of each good blood pressure data record

### Typical sequence:

- [client] BLE connect/GATT setup.
- [client] Read several standard device info characteristics from standard device info service.
- [client] Subscribe to indications from server-to-client command characteristic.
- [client] Subscribe to indications from blood pressure data characteristic.
- [device] Send challenge-response challenge (0xa1).
- [client] Send challenge-response response (0x20).
- [client] Set time offset in seconds since 2010-01-01 00:00:00 local time.
- [device] Send BP data records via indication to BP data characterisitic (0x8a91).
- [client] Send waiting for data command (0x22)
- ... repeat BP data + waiting for data until all BP data sent ...
- [device disconnects]

If the device doesn't accept the authentication response, the device will disconnect.

If the client's BLE stack fails to receive and acknowledge a BP data indication, the device will
disconnect (without sending further BP data nor retrying the failed indication).

Any blood pressure data which *is* received and acknowledged by the a subscribed client's BLE stack
will be deleted from the device's memory and not sent again. *Reading blood pressure data is a
destructive action. Each BP data item can only be read once.*

### Blood pressure data:

Blood pressure data is sent in 17-byte messages via indications to the blood pressure data
characteristic (0x8a91). After receipt of each good packet, write 0x22 to the client-to-server
command characteristic (0x8a81).

The format is:

 Offset | Type     | Description
--------|----------|-----------------------------------------------------------
 0      | uint8    | Header byte
 1      | uint16le | Systolic pressure (mmHg)
 3      | uint16le | Diastolic pressure (mmHg)
 5      | uint16le | *[unknown]*
 7      | uint32le | Timestamp in seconds since 2010-01-01 00:00:00 local time
 11     | uint16le | Heart rate (bpm)
 13     | uint8    | *[unknown]*
 14     | uint8    | BP data flags
 &nbsp; |          | 0x01 Motion detected during BP reading
 &nbsp; |          | 0x04 Irregular heartbeat detected during BP reading
 15     | uint8    | *[unknown]*
 16     | uint8    | Device flags
 &nbsp; |          | 0x01 Device battery level OK: 1 = OK, 0 = Low battery

## Future work

- Reduce blocking calls (e.g. `pprint.pformat()`, `logger.debug()`, etc.) in the BLE client to
  minimise risk of missed BLE data.
- Move BLE client into a separate thread to decouple from end-user blocking calls (like printing
  while reading from the `TranstekController.bpData()` async generator.
