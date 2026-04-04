
import logging
import bleak
import asyncio
import pprint
import argparse
import sys
import os

from .TranstekController import TranstekController
from .TranstekBleDriver import TranstekBleDriver
from .bleUuids import GattServices

bleak_logger = logging.getLogger("bleak")
logger = logging.getLogger(__name__)


async def client(args):
    bleak_logger.setLevel(logging.INFO)
    args.verbose = min(args.verbose, 3)
    match args.verbose:
        case 0:
            logging.basicConfig(level=logging.WARN)
        case 1:
            logging.basicConfig(level=logging.INFO)
        case 2:
            logging.basicConfig(level=logging.DEBUG)
        case 3:
            logging.basicConfig(level=logging.DEBUG)
            bleak_logger.setLevel(logging.DEBUG)

    # combine --proxy args with ESPHOME_BT_PROXIES env variable
    proxies = os.environ.get('ESPHOME_BT_PROXIES', '').split()
    proxies += args.proxy

    if proxies:
        try:
            from . import remote
        except ModuleNotFoundError as e:
            logger.error(f"Unable to import {e.name}. \n"
                         "To use bleak-esphome remote Bluetooth proxies, install the client with "
                         "`remote` optional dependencies:\n"
                         "    pip install welch-allyn-bp100-client[remote]")
            sys.exit(1)

        logger.info(
            "Using bleak-esphome remote Bluetooth proxies instead of system Bluetooth stack...")
        async with remote.bleakEsphomeProxies(
                [remote.proxyStringToConfig(proxy) for proxy in proxies]):
            await bluetoothConnect(targetAddress=args.device, password=args.password)
    else:
        await bluetoothConnect(targetAddress=args.device, password=args.password)


async def bluetoothConnect(targetAddress=None, password=None):
    if targetAddress is None:
        device, ad = await scanner()
        advName = ad.local_name
    else:
        logger.info(f"Connecting to specified BLE device with address {targetAddress}")
        device = targetAddress
        advName = None

    logger.info(f"Connecting to BP monitor {device} (advertised name {advName})...")

    transtekController = TranstekController(
                            TranstekBleDriver(device, advName=advName),
                            password=password
                            )

    # Once the controller is initialized, it will respond asynchronously
    # to BLE indications from the BP device.
    await transtekController.initialize()

    # wait until the client is disconnected before printing, etc.
    await transtekController.join()

    logger.info("BLE connection done!")

    pprint.pprint(transtekController.deviceInfo)
    async for bpData in transtekController.bpData():
        pprint.pprint(bpData)


async def scanner():
    # Normalized service UUIDs since Bleak will not match on a short/16 bit UUID
    serviceUuids = [bleak.uuids.normalize_uuid_str(u) for u in [GattServices.TRANSTEK_BP.value]]

    queue = asyncio.Queue()
    scanner = bleak.BleakScanner(
            detection_callback=lambda device, ad: queue.put_nowait((device, ad)),
            service_uuids=serviceUuids,
            )
    await scanner.start()

    try:
        logger.info(f"Scanning for service UUIDs {serviceUuids}...")
        device, ad = await queue.get()  # get a single item from queue
        logger.info(f"Got matching UUID: {ad.service_uuids} {ad.local_name}")
    finally:
        await scanner.stop()

    return device, ad


def argparseHexPasswordType(hexPassword):
    '''Convert 8 digit hex password to 4 bytes or error out'''
    # if password is not 8 hex digits, password will default to MAC-based password
    try:
        password = bytes.fromhex(hexPassword)
        if len(password) != 4:
            raise argparse.ArgumentTypeError(
                f"Password '{hexPassword}' must be 8 hex characters long.")
    except argparse.ArgumentTypeError:
        raise
    except:
        raise argparse.ArgumentTypeError(
                f"Password '{hexPassword}' cannot be decoded as hexadecimal.")
    return password


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-p",
        "--password",
        type=argparseHexPasswordType,
        default=None,
        help="Use provided password to connect to device. Should be 8 hex digits. Get the device "
             "password by holding the on/off button for two seconds when the device is off to "
             "enter paring mode, then running the `wa` script. The script will print the device "
             "password to the console. Note this password and provide it with subsequent runs if "
             "the script says that it differs from the default MAC-based password."
    )

    parser.add_argument(
        "--proxy",
        default=[],
        nargs='*',
        help="Configure a remote ESPHome Bluetooth Proxy to use instead of native Bluetooth stack. "
             "Proxies should be specified as a colon-delimited string:\n"
             "    --proxy <proxy address>:<noise PSK>\n"
             "Multiple --proxy arguments may be specified. Alternatively, multiple space-delimited "
             "configs of the same <address>:<psk> format may be specified in an environment "
             "variable:\n"
             "    ESPHOME_BT_PROXIES=\"<address>:<psk> <address:psk> ...\" wa ...\n"
             "Using the environment variable is more secure, since it avoids exposing your "
             "proxies' PSKs in the system process list."
    )

    parser.add_argument(
        "-v",
        "--verbose",
        default=0,
        action="count",
        help="Set logging verbosity. Specify multiple times for more detail.",
    )

    parser.add_argument(
        "device",
        nargs="?",
        default=None,
        help="BLE device MAC address (or, on MacOS, device UUID) to connect to instead of scanning"
             "for advertising devices."
    )

    args = parser.parse_args()
    await client(args)

    return 0


def run():
    return asyncio.run(main())

if __name__ == '__main__':
    sys.exit(run())
