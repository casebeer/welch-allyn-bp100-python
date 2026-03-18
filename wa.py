
from bleak import (
  BleakClient,
  BleakScanner,
)

import logging
bleak_logger = logging.getLogger("bleak")
bleak_logger.setLevel(logging.DEBUG)


import asyncio
import sys

from transtek import (
  TranstekController,
  TranstekBleDriver,
  MockTranstekBleDriver,
)

from transtek.bleUuids import (
  TRANSTEK_BP_SERVICE,
  DEVICE_INFO_SERVICE,
)

async def main():
  logging.basicConfig(level=logging.DEBUG)
  password = bytearray.fromhex(sys.argv[1])

  # TODO: Data storage handler for password, bp data, and low battery status
  #transtekController = TranstekController(MockTranstekBleDriver(), bytearray([ 0xaa, 0xbb, 0xcc, 0xdd ]))
  #await transtekController.initialize()
  #return

  print("Scanning for BLE devices...")
#  device = await BleakScanner.find_device_by_filter(
#    filterfunc = foobar,
#    return_adv = False,
#    timeout = 60,
#    service_uuids=[TRANSTEK_BP_SERVICE],
#    )
##  filters={"UUIDs":["1d93af38-9239-11ea-bb37-0242ac130002"], "DuplicateData":False}
#  devices = await BleakScanner.discover(
#    return_adv = False,
#    timeout = 60,
#    service_uuids=[TRANSTEK_BP_SERVICE.lower()],
#    )
#
#  if len(devices) == 0:
#    print("No devices found. Exiting.")
#    return
#  else:
#    device = devices[0]


  async with BleakScanner(
    service_uuids = [TRANSTEK_BP_SERVICE],
    ) as scanner:
    print("Scanning...")

    print(f"\nadvertisement packets:")
    async for bleDevice, advertisementData in scanner.advertisement_data():
      if advertisementData.service_uuids:
        print(f"{advertisementData.service_uuids}")
        #print(f" {bd!r} with {ad!r}")
        if TRANSTEK_BP_SERVICE.lower() in advertisementData.service_uuids:
          print("Found matching device!")
          device = bleDevice
          break
    print("Broken out of scanning loop...")


  print("Found BP monitor device.")
  print(device)

  print("Connecting to BP monitor...")
  #async with BleakClient(device) as client:
  client = BleakClient(device)
  #model_number = await client.read_gatt_char(MANUFACTURER_NAME_CHAR)
  #print("Model number = {}".format(model_number))

  await client.connect()

  transtekController = TranstekController(TranstekBleDriver(client), password)
  await transtekController.initialize()
  await asyncio.sleep(1000)


if __name__ == '__main__':
  asyncio.run(main())
