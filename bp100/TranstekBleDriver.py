import logging

from bleak import (
    BleakClient,
)

import asyncio
import pprint

from bleak import (
    BleakGATTCharacteristic,
)
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
    retry_bluetooth_connection_error,
)

from .bleUuids import (
    GattServices,
    TranstekCharacteristics,
)

logger = logging.getLogger(__name__)
BLE_CONNECT_TIMEOUT_SECONDS = 60

class TranstekBleDriver(object):
    def __init__(self, deviceOrAddress, advName=None):
        self.deviceOrAddress = deviceOrAddress
        self.deviceName = advName if advName is not None else \
                            getattr(deviceOrAddress, 'name',
                            getattr(deviceOrAddress, 'address',
                            f"TranstekBleDevice str(deviceOrAddress)"))
        self.is_connected = False
        self.finished = asyncio.Event()

    #@retry_bluetooth_connection_error
    async def connect(self):
        self.client = await establish_connection(
            BleakClientWithServiceCache,
            self.deviceOrAddress,
            self.deviceName,
            disconnected_callback=lambda client: asyncio.create_task(self.disconnect()),
            timeout=BLE_CONNECT_TIMEOUT_SECONDS
        )
        try:
            self.bpService = self.client.services.get_service(
                                    GattServices.TRANSTEK_BP.value)
            self.bpChar = self.bpService.get_characteristic(
                                    TranstekCharacteristics.BP_DATA_INDICATE.value)
            self.c2sCommandChar = self.bpService.get_characteristic(
                                    TranstekCharacteristics.C2S_COMMAND.value)
            self.s2cCommandChar = self.bpService.get_characteristic(
                                    TranstekCharacteristics.S2C_COMMAND_INDICATE.value)

            self.is_connected = self.client.is_connected

            logger.info(f"Connected to device {self.client.address} ({self.deviceName})")
            logger.debug(self.formatGattInfo())
        except BleakError as e:
            logger.warn(f"BleakError setting up Transtek BLE client: {e}, disconnecting")
            self.disconnect()

    async def disconnect(self):
        logger.debug("Disconnecting and cleaning up TranstekBleDriver...")
        # cleanup
        try:
            if self.client.is_connected:
                await self.client.disconnect()
        finally:
            self.is_connected = False
            self.finished.set()

    async def join(self):
        '''Wait until this bleDriver's BleakClient has disconnected'''
        if not self.is_connected:
            return
        await self.finished.wait()


    def formatGattInfo(self):
        services = self.client.services.services
        chars = self.client.services.characteristics
        descs = self.client.services.descriptors

        response = []
        response.append(pprint.pformat({
            f"handle 0x{k:04x}": f"{v.description} ({v.uuid})" for (k, v) in services.items()
        }))
        response.append(pprint.pformat({
            f"handle 0x{k:04x}": f"{v.description} ({v.uuid}) {v.properties}" for (k, v) in chars.items()
        }))
        response.append(pprint.pformat({
            f"handle 0x{k:04x}": f"{v.description} ({v.uuid}) for {v.characteristic_uuid} (handle {v.characteristic_handle:04x})" for (k, v) in descs.items()
        }))

        response.append(formatGattInfo((self.client)))

        return "\n".join(response)

    async def subscribeToCommands(self, handler):
        async def wrapper(characteristic: BleakGATTCharacteristic, data: bytearray):
            logger.debug(f"[wrapper] command characteristic callback: {data.hex()}")
            return await handler(data)
        await self.client.start_notify(self.s2cCommandChar, wrapper)

    async def subscribeToBpData(self, handler):
        async def wrapper(characteristic: BleakGATTCharacteristic, data: bytearray):
            logger.debug(f"[wrapper] bpdata characteristic callback: {data.hex()}")
            return await handler(data)
        await self.client.start_notify(self.bpChar, wrapper)

    async def readDeviceInfoCharacteristic(self, char):
        return await self.client.read_gatt_char(char)

    async def writeCommand(self, commandBytes):
        retries = 3
        while retries > 0:
            retries -= 1
            if not self.is_connected:
                break
            try:
                logger.debug(f"Sending command to server: {commandBytes.hex()}")
                await self.client.write_gatt_char(self.c2sCommandChar, commandBytes, response=True)
                return
            except Exception as e:
                logger.error(f"Problem writing to command characteristic. client.is_connected = {self.client.is_connected} Error: {e}")


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


def shortenUuidString(uuid):
    # Format 16- and 32-bit UUIDs as short hex strings
    # remove BLE base UUID suffix and convert to numeric value
    value = int(uuid[:8], 16)
    # print as 4 or 8 nibble hex string
    if value < 2**16:
        return f"0x{value:04x}"
    else:
        return f"0x{value:08x}"


def formatGattInfo(client):
    services = client.services.services
    chars = client.services.characteristics
    descs = client.services.descriptors

    response = []
    for handle, service in services.items():
        response.append(f"{formatHandle(handle)} \"{service.description}\" service ({shortenUuidString(service.uuid)})")
        for char in service.characteristics:
            response.append(f"    {formatHandle(char.handle)} char {char.description} ({shortenUuidString(char.uuid)}) {char.properties}")
            for desc in char.descriptors:
                response.append(f"        {formatHandle(desc.handle)} desc {desc.description} ({shortenUuidString(desc.uuid)})")
    return "\n".join(response)
