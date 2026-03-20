
import bleak
from bleak import (
    BleakScanner,
)

import logging
bleak_logger = logging.getLogger("bleak")
#bleak_logger.setLevel(logging.DEBUG)
bleak_logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)


import asyncio
import sys
import os
import pprint

from surebp import (
    TranstekController,
    TranstekBleDriver,
    #MockTranstekBleDriver,
)

from surebp.bleUuids import (
    GattServices,
)

async def main():
    #logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    password = bytearray.fromhex(os.environ.get('WA_BLE_PASSWORD', ''))

    # optional device address – connect directly to device without waiting for advertisements
    deviceAddress = sys.argv[1] if len(sys.argv) > 1 else None

    if not password:
        raise Exception("You must provide the 4-byte BLE device 'password' as an 8-hex-digit "
                        "string in the WA_BLE_PASSWORD environment variable. "
                        "\ne.g. WA_BLE_PASSWORD=aabbccdd python wa.py")

    # TODO: Data storage handler for password, bp data, and low battery status
    #transtekController = TranstekController(MockTranstekBleDriver(), bytearray([ 0xaa, 0xbb, 0xcc, 0xdd ]))
    #await transtekController.initialize()
    #return

#    device = await BleakScanner.find_device_by_filter(
#        filterfunc = foobar,
#        return_adv = False,
#        timeout = 60,
#        service_uuids=[GattServices.TRANSTEK_BP.value],
#        )
##    filters={"UUIDs":["1d93af38-9239-11ea-bb37-0242ac130002"], "DuplicateData":False}
#    devices = await BleakScanner.discover(
#        return_adv = False,
#        timeout = 60,
#        service_uuids=[GattServices.TRANSTEK_BP.value.lower()],
#        )
#
#    if len(devices) == 0:
#        logger.info("No devices found. Exiting.")
#        return
#    else:
#        device = devices[0]

    if deviceAddress is None:
        logger.info("Scanning for BLE devices...")
        # Normalized service UUIDs since Bleak will not match on a short/16 bit UUID
        serviceUuids = [bleak.uuids.normalize_uuid_str(u) for u in [GattServices.TRANSTEK_BP.value]]
        async with BleakScanner(
            service_uuids=serviceUuids,
            ) as scanner:
            logger.info(f"Scanning for service UUIDs {serviceUuids}...")

            logger.info(f"\nadvertisement packets:")
            async for bleDevice, advertisementData in scanner.advertisement_data():
                if advertisementData.service_uuids:
                    logger.info(f"Got matching UUID: {advertisementData.service_uuids}")
                    # return the first matching device seen
                    device = bleDevice
                    break
            logger.info("Broken out of scanning loop...")
        logger.info("Found BP monitor device.")
    else:
        logger.info(f"Connecting to specified BLE device with address {deviceAddress}")
        device = deviceAddress
    logger.info(device)

    logger.info("Connecting to BP monitor...")

#    async with BleakClient(
#        device,
#        disconnected_callback=clientDisconnect,
#        timeout=BLE_CONNECT_TIMEOUT_SECONDS
#        ) as client:
#        #model_number = await client.read_gatt_char(MANUFACTURER_NAME_CHAR)
#        #logger.info("Model number = {}".format(model_number))
#
#        await client.connect()

    transtekController = TranstekController(TranstekBleDriver(device), password)

    # Once the controller is initialized, it will respond asynchronously
    # to BLE indications from the BP device.
    await transtekController.initialize()

    # wait until the client is disconnected before printing, etc.

    async for bpData in transtekController.bpData():
        pprint.pprint(bpData)

    print("BLE controller out of data")
    await transtekController.join()

    print("BLE connection done!")


def clientDisconnect(client):
    # BleakClient disconnect callback
    logger.info("Client disconnected.")
if __name__ == '__main__':
    asyncio.run(main())
