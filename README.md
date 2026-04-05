# Welch Allyn 1500 & 1700 BP100 Python Client

Python client for Welch Allyn model 1500 and 1700 BP100 BLE home blood pressure meters. Uses the
Bleak Python BLE library.

These devices require a Welch Allyn Android app which is no longer practically installable, as it
has not been updated to support modern 64 bit Android (as of June 2025). (Update: There appears to
be a new official Android app as of March 2026).

## Devices and compatibility

Tested with the Welch Allyn 1700 SureBP H-BP100-SBP device (both "Ver. A" and "Ver. B").

Likely also works with the Welch Allyn 1500 RPM-BP100 device.

These devices appear to use a BLE chipset and protocol from Transtek. The bulk of the code handling
this protocol is in the `bp100` package in this project.

- Tested on MacOS 15 with Python 3.14.
- Tested on Linux with Home Assistant remote ESPHome Bluetooth proxies.
- Tested partially working/slow/unreliable on Linux with Bluez 5.8.3 (may be adapter issue).

## Installation

    git clone https://github.com/casebeer/welch-allyn-bp100-python
    cd welch-allyn-bp100-python
    python3 -m venv venv
    venv/bin/pip install -U pip && venv/bin/pip install -e .

## Usage

You'll need:

1. A Welch Allyn BP100 device, like the 1700/H-BP100-SBP.

*Note that using this script will download all blood pressure readings still on the device. Once a
blood pressure reading has been downloaded by any app, it is erased from the device and will NOT be
available for reading by the official Welch Allyn app.*

Use the `wa` CLI script (`bp100/cli.py`) to test connection to your blood pressure monitor.

First, start the script:

    venv/bin/wa

Now, use the blood pressure meter to take a reading. Once the reading completes, the blood pressure
device will broadcast via BLE.

The `wa` script should receive this broadcast, connect to the device, and download and print out
all blood pressure readings on the device. Note that the device will only send each BP reading once,
to one client, so after reading, there will be no BP data stored on the device.

If you've used the BP device to take multiple readings without downloading them, the script should
read and delete all of them from the device. If there are no stored readings, the script should get
only one (the current) reading.

You can also specify an exact device BLE address (or, on MacOS, a device address UUID), and the
script will attempt to connect to that device rather than wait to receive an advertisement:

    venv/bin/wa [BLE address or UUID]

If you want a little more information about what's happening during the connection, use the
`--verbose`/`-v` option one or more times:

    wa -v # INFO level logging to stderr
    wa -vv # DEBUG level logging to stderr

To specify a four byte password rather than have the library guess a password based on the GATT
serial number/MAC, pass the `--password`/`-p` argument with 8 hex characters:

    wa --password aabbccdd

### ESPHome remote Bluetooth proxies

This library supports using ESPHome remote Bluetooth proxies via the `bleak-esphome` package.

Remote proxies enable using Bluetooth over the network from machines with no actual Bluetooth
hardware directly connected (or machines positioned in a poor RF location). See
[`bleak-esphome`](https://github.com/Bluetooth-Devices/bleak-esphome) for example proxy client code
and the [ESPHome Bluetooth Proxies documentation](https://esphome.io/components/bluetooth_proxy/),
[ESPHome Bluetooth Proxy sample YAML configs](https://github.com/esphome/bluetooth-proxies), or
[ESPHome Ready-Made Projects web-based device flasher](https://esphome.io/projects/) for information
on flashing an ESP32 microcontroller with ESPHome firmware configured as a Bluetooth proxy.

Install dependencies supporting remote proxies with the `remote` optional dependencies target:

    pip install -e .[remote]

To use this feature from the CLI, you can either pass the `--proxy` CLI argument or use the
`ESPHOME_BT_PROXIES` environment variable:

    wa -v --proxy <proxy address>:<psk> --proxy <proxy address 2>:<psk 2>

Or with the environment variable:

    ESPHOME_BT_PROXIES="<address1>:<psk1> <address2>:<psk2>" wa -v

Using the environment variable is more secure, since the CLI argument will expose your Noise PSKs in
the system process list.

Note that you *cannot* simultaneously connect to an ESPHome proxy device already in use by Home
Assistant. ESPHome devices support only a single Bluetooth proxy connection at a time, with the
first device to connect locking out subsequent connection attempts.

Unfortunately, the ESPHome API does not send any errors or feedback when a proxy initialization
fails. To determine if failure to see any BLE traffic is due to connection contention, view your
ESPHome device's logs while you attempt to connect. Failures will appear in the ESP32 logs as
`[bluetooth_proxy:...]: Only one API subscription is allowed at a time`.

## API

For API usage, see the `bp100/cli.py` script that provides the `wa` CLI entrypoint. Basics:

    import asyncio
    import pprint
    import bleak

    from bp100 import (TranstekController, TranstekBleDriver, GattServices)

    async def run():
        # Use BleakScanner to find your device by advertised service UUID
        async with bleak.BleakScanner(
            service_uuids=[bleak.uuids.normalize_uuid_str(GattServices.TRANSTEK_BP.value)],
            ) as scanner:
            print("Scanning...")

            async for device, ad in scanner.advertisement_data():
                if ad.service_uuids:
                    print(f"Got matching UUID: {ad.service_uuids} ({ad.local_name})")
                    # return the first matching device seen
                    break

        # Pass the discovered BLEDevice to the client
        # You could alternatively provide a BLE address (or on MacOS, UUID) in place of `device`
        # and skip the discovery entirely
        controller = TranstekController(TranstekBleDriver(device, advName=ad.local_name))

        # Initialize the controller
        await controller.initialize()

        # Wait for all data to finish downloading. Avoid print() and other blocking calls until
        # BLE data download is done to avoid breaking BLE timing
        await controller.join()

        # Print out the device data
        pprint.pprint(controller.deviceInfo)

        # Iterate over and print out the discovered BP data
        async for data in controller.bpData():
            pprint.pprint(data)

    asyncio.run(run())

See `cli.py` and `remote.py` for usage via `bleak-esphome` remote proxies. Remote proxies require
(a) NOT using `from ... import` for BleakClient* and BleakScanner instances, and (b) NOT using the
`async with` Bleak APIs.

## Testing

Install with `test` dependencies and use `pytest`:

    pip install -e .[test]
    pytest

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

Transtek (OEM for Welch Allyn BP100 models 1500 and 1700) BLE blood pressure monitors
exchange commands with the client via client writes to a client-to-sever characteristic and device
indications to a server-to-client characteristic subscribed to by the client.

Before sending actual blood pressure data, the device requires the client to authenticate via a
trivial challenge-response password authentication over the command characteristics.

This "password" appears to be the last 8 hex chars of the reported device info serial number,
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

- Take a blood pressure reading with the device. BLE activity begins when the Bluetooth symbol
  begings flashing after the reading is complete.
- [device] Sends BLE advertisements after BP reading is finished
- [client] BLE connect/GATT setup.
- [client] Read several standard device info characteristics from standard device info service.
- [client] Subscribe to indications from server-to-client command characteristic.
- [client] Subscribe to indications from blood pressure data characteristic.
- [device] Send challenge-response challenge (0xa1).
- [client] Send challenge-response response (0x20).
- [client] Set time offset in seconds since 2010-01-01 00:00:00 local time. If this write fails
  and/or the device terminates the connection at this point, the device has rejected the password we
  used to compute the authentication response.
- [device] Send BP data records via indication to BP data characterisitic (0x8a91).
- [client] Send waiting for data command (0x22)
- ... repeat BP data + waiting for data until all BP data sent ...
- [device disconnects]

If the device doesn't accept the authentication response, the device will disconnect.

If the client's BLE stack fails to receive and acknowledge a BP data indication, the device will
disconnect (without sending further BP data nor retrying the failed indication). Timing of these
responses is crticial. Delays even due to inline `print()` calls can cause BP data read failures.

Any blood pressure data which *is* received and acknowledged by the a subscribed client's BLE stack
will be deleted from the device's memory and not sent again. *Reading blood pressure data is a
destructive action. Each BP data item can only be read once.*

### Pairing sequence (and "password" receipt)

A pairing sequence begins when the blood pressure device is started in pairing mode, by pressing and
holding the on/off button for two seconds while the device is off.

The device will beging sending BLE advertisements immediately without taking a blood pressure
reading.

BLE pairing sequence:

- Press and hold device on/off button while the device is off to enter pairing mode.
- [device] Sends BLE advertisements immediately
- [client] BLE connect/GATT setup.
- [client] Read several standard device info characteristics from standard device info service.
- [client] Subscribe to indications from server-to-client command characteristic.
- [client] Subscribe to indications from blood pressure data characteristic.
- **[device] Send password (0xa0).**
- **[client] Send setBroadcastId (0x21).**
- [device] Send challenge-response challenge (0xa1).
- [client] Send challenge-response response (0x20).
- [client] Set time offset in seconds since 2010-01-01 00:00:00 local time.
- **[client] Send waiting for data command (0x22)**
- [device disconnects]

When in pairing mode, the device's BLE advertisement name will be `1BP100`.

When not in pairing mode, the device's advertised name will begin with `0BP100`, followed by the hex
string representation of the four bytes sent by the client with the `0x21` `setBroadcastId` command
during pairing. Typically this is `0BP10001234567`.

Note that to see the advertised name, you should read the `ad.local_name` field from a
`BleakScanner()` callback, not the `device.name` field, which may be cached by the OS:

    async with bleak.BleakScanner(
        service_uuids=[bleak.uuids.normalize_uuid_str(GattServices.TRANSTEK_BP.value)],
        ) as scanner:
        async for device, ad in scanner.advertisement_data():
            print(f"advertised name: {ad.local_name} cached name: {device.name}")

#### Receiving the "password" via pairing

A four byte "password" is required to connect to the BP device and download data. Normally, this
library derives that password from the serial number reported by the device.

When connected to in pairing mode (by holding the on/off button for two seconds while the device is
off), the device will send the `0xa0` "setPassword" command with the long term password needed to
connect to the device in the future.

#### Deriving the password from the MAC

This password appears to be hard-coded per device and based on the device's Bluetooth MAC address.

I've seen two variants: one that uses the last four bytes of the little-endian (wire format) MAC
address, and one that uses the first four bytes.

Note that Bluetooth MAC addresses (a.k.a. BDADDR) are always displayed in big-endian format, but the
wire format in a Bluetooth packet is little-endian.

Additionally, since on MacOS the actual Bluetooth MACs are not accessible for privacy reasons, this
library derives the BDADDR from the "serial number" characteristic of the GATT device information
service. There are at least two different variations of the GATT serial number: one holding the
little-endian wire format MAC, and one holding the big-endian display-format MAC.

This gives four possible ways to derive the hardcoded password:

1. Serial number is little-endian/wire MAC, password is last 4 bytes of little-endian/wire MAC
   (seen on older H-BP100SBP model 1700 device with detachable BP cuff and marking "Ver. A"
   on sticker)
2. Serial number is big-endian/display MAC, password is first 4 bytes of little-endian/wire MAC
   (seen on newer H-BP100SBP device with non-detachable BP cuff and marking "Ver. B" on sticker)
3. Serial number is little-endian/wire MAC, password is first 4 bytes of little-endian/wire MAC
4. Serial number is big-endian/display MAC, password is last 4 bytes of little-endian/wire MAC

By default, this library will try each of these four password variants, in this order. To prevent
this, specify a password when creating a `TranstekController` instance or pass the `--password`
argument to the `wa` CLI program.

If you receive an `0xa0` `setPassword` command whose password does *not* match any of these
MAC-derived passwords, you should store that received password long term for use in future
transactions. The `0xa0` password notification is only sent when the device is in pairing mode.

Worked examples:

Assume the Bluetooth MAC address is `12:34:56:78:90:ab`. This MAC is in big-endian/display format,
as it would appear e.g. on the sticker on the back of the device.

Using password strategy (1), i.e. the GATT serial number is the *little-endian/wire format* of the
MAC, and the password is *last* four bytes of little-endian MAC:

- GATT serial number: "AB9078563412"
- Little-endian Bluetooth MAC: `ab9078563412`
- Password: `78563412` (last four bytes of little-endian MAC)

Alternatively, using password strategy (2), i.e. the GATT serial number is the *big-endian/display
format* of the MAC, and the password is *first* four bytes of little-endian MAC:

- GATT serial number: "1234567890AB"
- Little-endian Bluetooth MAC: `ab9078563412`
- Password: `ab907856` (first four bytes of little-endian MAC)

### Blood pressure data:

Blood pressure data is sent in 17-byte messages via indications to the blood pressure data
characteristic (0x8a91). After receipt of each good packet, write 0x22 to the client-to-server
command characteristic (0x8a81).

The format is:

 Offset | Type     | Description
--------|----------|-----------------------------------------------------------
 0      | uint8    | Header byte 0x34
 1      | uint16le | Systolic pressure (mmHg)
 3      | uint16le | Diastolic pressure (mmHg)
 5      | uint16le | *[unknown]* observed 0x0000
 7      | uint32le | Timestamp in seconds since 2010-01-01 00:00:00 local time
 11     | uint16le | Heart rate (bpm)
 13     | uint8    | *[unknown]* observed 0x01
 14     | uint8    | BP data flags
 &nbsp; |          | 0x01 Motion detected during BP reading
 &nbsp; |          | 0x04 Irregular heartbeat detected during BP reading
 15     | uint8    | *[unknown]* observed 0x00
 16     | uint8    | Device flags
 &nbsp; |          | 0x01 Device battery level OK: 1 = OK, 0 = Low battery

## Future work

- Reduce blocking calls (e.g. `pprint.pformat()`, `logger.debug()`, etc.) in the BLE client to
  minimise risk of missed BLE data.
- Move BLE client into a separate thread to decouple from end-user blocking calls (like printing
  while reading from the `TranstekController.bpData()` async generator.
