
import logging
import bleak
import asyncio
import pprint
import argparse
import sys

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

    if args.device is None:
        # Normalized service UUIDs since Bleak will not match on a short/16 bit UUID
        serviceUuids = [bleak.uuids.normalize_uuid_str(u) for u in [GattServices.TRANSTEK_BP.value]]
        async with bleak.BleakScanner(
            service_uuids=serviceUuids,
            ) as scanner:
            logger.info(f"Scanning for service UUIDs {serviceUuids}...")

            async for bleDevice, advertisementData in scanner.advertisement_data():
                if advertisementData.service_uuids:
                    logger.info(f"Got matching UUID: {advertisementData.service_uuids}")
                    # return the first matching device seen
                    device = bleDevice
                    break
            logger.debug("Broken out of scanning loop...")
    else:
        logger.info(f"Connecting to specified BLE device with address {args.device}")
        device = args.device

    logger.info(f"Connecting to BP monitor {device}...")

    transtekController = TranstekController(TranstekBleDriver(device))

    # Once the controller is initialized, it will respond asynchronously
    # to BLE indications from the BP device.
    await transtekController.initialize()

    # wait until the client is disconnected before printing, etc.
    await transtekController.join()

    logger.info("BLE connection done!")

    pprint.pprint(transtekController.deviceInfo)
    async for bpData in transtekController.bpData():
        pprint.pprint(bpData)

async def main():
    parser = argparse.ArgumentParser()

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
