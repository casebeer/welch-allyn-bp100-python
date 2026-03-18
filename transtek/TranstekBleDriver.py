import logging
logger = logging.getLogger(__name__)

import pprint

from bleak import (
  BleakGATTCharacteristic,
)

from .bleUuids import (
  TRANSTEK_BP_SERVICE,
  TRANSTEK_BP_DATA_INDICATE_CHAR,
  TRANSTEK_BP_DATA_NOTIFY_CHAR,
  TRANSTEK_C2S_COMMAND_CHAR,
  TRANSTEK_S2C_COMMAND_INDICATE_CHAR,
)

class TranstekBleDriver(object):
  def __init__(self, client):
    self.client = client
    self.bpService = self.client.services.get_service(TRANSTEK_BP_SERVICE)
    self.bpChar = self.bpService.get_characteristic(TRANSTEK_BP_DATA_INDICATE_CHAR)
    self.c2sCommandChar = self.bpService.get_characteristic(TRANSTEK_C2S_COMMAND_CHAR)
    self.s2cCommandChar = self.bpService.get_characteristic(TRANSTEK_S2C_COMMAND_INDICATE_CHAR)

    self.printGattInfo()

  def printGattInfo(self):
    services = self.client.services.services
    chars = self.client.services.characteristics
    descs = self.client.services.descriptors
    pprint.pprint({
      f"handle 0x{k:04x}": f"{v.description} ({v.uuid})" for (k, v) in services.items()
    })
    pprint.pprint({
      f"handle 0x{k:04x}": f"{v.description} ({v.uuid}) {v.properties}" for (k, v) in chars.items()
    })
    pprint.pprint({
      f"handle 0x{k:04x}": f"{v.description} ({v.uuid}) for {v.characteristic_uuid} (handle {v.characteristic_handle:04x})" for (k, v) in descs.items()
    })

    printGattInfo(self.client)

  async def subscribeToCommands(self, handler):
    async def wrapper(characteristic: BleakGATTCharacteristic, data: bytearray):
      print(f"[wrapper] command characteristic callback: {data.hex()}")
      return await handler(data)
    #await self.client.start_notify(TRANSTEK_S2C_COMMAND_INDICATE_CHAR, wrapper)
    await self.client.start_notify(self.s2cCommandChar, wrapper)

  async def subscribeToBpData(self, handler):
    async def wrapper(characteristic: BleakGATTCharacteristic, data: bytearray):
      print(f"[wrapper] bpdata characteristic callback: {data.hex()}")
      return await handler(data)
    #await self.client.start_notify(TRANSTEK_BP_DATA_INDICATE_CHAR, wrapper)
    await self.client.start_notify(self.bpChar, wrapper)

  async def readDeviceInfoCharacteristic(self, char):
    return await self.client.read_gatt_char(char)

  async def writeCommand(self, commandBytes):
    retries = 3
    while retries > 0:
      retries -= 1
      try:
        logger.debug(f"Sending command to server: {commandBytes.hex()}")
        await self.client.write_gatt_char(self.c2sCommandChar, commandBytes, response=True)
        return
      except Exception as e:
        logger.error(f"Problem writing to command characteristic. client.is_connected = {self.client.is_connected} Error: {e}")
        if not self.client.is_connected:
          logger.info(f"Attempting to reconnect client... ({retries} retries remain)")
          await self.client.connect()



def gattInfo(client):
  services = client.services.services
  chars = client.services.characteristics
  descs = client.services.descriptors

  return {
    "services": {
      f"handle 0x{k:04x}": {
        "description": v.description,
        "uuid": v.uuid,
        "characteristics": {
          f"handle 0x{k:04x}": {
            "description": v.description,
            "uuid": v.uuid,
            "properties": v.properties,
          } for (k, v) in chars.items()
        }
      }
      for (k, v) in services.items()
    },
    "descriptors": {
      f"handle 0x{k:04x}": {
        "description": v.description,
        "uuid": v.uuid,
        "characteristic": f"{v.characteristic_uuid} (handle {v.characteristic_handle:04x})"
      } for (k, v) in descs.items()
    },
  }

def formatHandle(handle):
  return f"0x{handle:02x}:"
# Format 16- and 32-bit UUIDs as short hex strings
def shortenUuidString(uuid):
  # remove BLE base UUID suffix and convert to numeric value
  value = int(uuid[:8], 16)
  # print as 4 or 8 nibble hex string
  if value < 2**16:
    return f"0x{value:04x}"
  else:
    return f"0x{value:08x}"
def printGattInfo(client):
  services = client.services.services
  chars = client.services.characteristics
  descs = client.services.descriptors

  for handle, service in services.items():
    print(f"{formatHandle(handle)} \"{service.description}\" service ({shortenUuidString(service.uuid)})")
    for char in service.characteristics:
      print(f"  {formatHandle(char.handle)} char {char.description} ({shortenUuidString(char.uuid)}) {char.properties}")
      for desc in char.descriptors:
        print(f"    {formatHandle(desc.handle)} desc {desc.description} ({shortenUuidString(desc.uuid)})")
