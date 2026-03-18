
from .bleUuids import (
  MODEL_NUMBER_CHAR,
  SERIAL_NUMBER_CHAR,
  FIRMWARE_REVISION_CHAR,
  HARDWARE_REVISION_CHAR,
  SOFTWARE_REVISION_CHAR,
  MANUFACTURER_NAME_CHAR,
)

from .TranstekBleDriver import TranstekBleDriver

import pprint
import asyncio

from . import util

BLE_RESPONSE_DELAY = 0.01 # slow down messages sent to GATT server

'''
# TranstekController

Coordinate BLE indication subscriptions and writes for Transtek BLE BP monitor.

Transtek (OEM for Welch Allyn SureBP BP100 models 1500 and 1700) BLE blood pressure monitors
exchange commands with the client via writes to a client-to-sever characteristic and indicate
subscriptsions to a server-to-client characteristic.

Before sending actual blood pressure data, the device requires the client to authenticate via a
trivial challenge-response password authentication over the command characteristics.

The BP monitor device server sends actual blood pressure data to the client via indications to a
separate blood pressure data characteristic once authentication is complete.

## Characteristics of the Transtek BP service (0x7809)

- 0x8a81 Client-to-server command characteristic (write)
- 0x8a82 Server-to-client command characteristic (indicate)
- 0x8a91 BP data characteristic (indicate)

## Command structure

Command data sent via the two command characteristics consists of one byte specifying the command
followed by between zero and four bytes of data, depending on the specific command.

Multi-byte data fields (in both commands and blood pressure data) are little endian unsigned
16-bit or 32-bit integers.

### Known commands:

- [s2c] 0xa0 <uint32le> setPassword(password) Set long-term password for use in challenge-response
- [c2s] 0x21 <uint32le> setBroadcastID(broadcastId) Always set as 0x01 0x23 0x45 0x67
- [s2c] 0xa1 <uint32le> setChallenge(challenge) Issue random four byte authentication challenge
- [c2s] 0x20 <uint32le> setChallengeResponse(response) Auth response = challenge xor password
- [c2s] 0x02 <uint32le> setTime(timestampSeconds) Set localtime in seconds since 2010-01-01
- [s2c] 0x22 aboutToDisconnect()
- [c2s] 0x22 waitingForData() Sent after receipte of each good blood pressure data record

## Typical sequence:

[client] BLE connect.
[client] Read several standard device info characteristics from standard device info service.
[client] Subscribe to indications from server-to-client command characteristic.
[client] Subscribe to indications from blood pressure data characteristic.
[device] Send challenge-response challenge (0xa1).
[client] Send challenge-response response (0x20).
[client] Set time offset in seconds since 2010-01-01 00:00:00 local time.
[device] Send BP data records via indication to BP data characterisitic (0x8a91).
[client] Send waiting for data command (0x22)
... repeat BP data + waiting for data until all BP data sent ...
<device disconnects>

## Pairing:

TBD

## Blood pressure data:

Blood pressure data is sent in 17-byte messages via indications to the blood pressure data
characteristic (0x8a91). After receipt of each good packet, write 0x22 to the client-to-server
command characteristic (0x8a81).

The format is:

 -  [0] uint8    Header byte
 -  [1] uint16le Systolic pressure (mmHg)
 -  [3] uint16le Diastolic pressure (mmHg)
 -  [5] uint16le <unknown>
 -  [7] uint32le Timestamp in seconds since 2010-01-01 00:00:00 local time
 - [11] uint16le Heart rate (bpm)
 - [13] uint8    <unkown>
 - [14] uint8    BP data flags
                 0x01 Motion detected during BP reading
                 0x04 Irregular heartbeat detected during BP reading
 - [15] uint8    <unknown>
 - [16] uint8    Device flags
                 0x01 Device battery level OK: 1 = OK, 0 = Low battery
'''
class TranstekController(object):
  deviceInfoFields = [
    ('Manufacturer name', MANUFACTURER_NAME_CHAR),
    ('Firmware revision', FIRMWARE_REVISION_CHAR),
    ('Hardware revision', HARDWARE_REVISION_CHAR),
    ('Software revision', SOFTWARE_REVISION_CHAR),
    ('Model number', MODEL_NUMBER_CHAR),
    ('Serial number', SERIAL_NUMBER_CHAR),
  ]
  def __init__(self, bleDriver, password: bytearray):
    self.bleDriver = bleDriver
    self.password = password
  async def initialize(self):
    print("Initializing Transted BLE client...")
    self.deviceInfo = await self.getDeviceInfo() # TODO: handle deviceInfo
    #self.deviceInfo = {}
    pprint.pprint(self.deviceInfo)

    await self.bleDriver.subscribeToBpData(self.bpDataHandler)
    await self.bleDriver.subscribeToCommands(self.commandHandler)

    print("BLE indications configured.")
  async def commandHandler(self, data: bytearray):
    print(f"[s2c] {data.hex()}")
    match data[0]:
      case 0xa0:
        self.setPassword(data[1:5])
        await self.setBroadcastId()
        #asyncio.get_event_loop().create_task(self.setBroadcastId())
      case 0xa1:
        await self.setChallenge(data[1:5])
        await self.setTime()
        #asyncio.get_event_loop().create_task(self.setChallenge(data[1:5]))
        #asyncio.get_event_loop().create_task(self.setTime())
        # TODO: if pairing, then self.setWaitingForData()
      case 0x22:
        print("[s2c] 0x22 deviceWillDisconnect")
      case _:
        pass
  async def bpDataHandler(self, dataBytes: bytearray):
    data = util.parseBpData(dataBytes)
    pprint.pprint(data)
    await self.setWaitingForData()
    #asyncio.get_event_loop().create_task(self.setWaitingForData())
  async def getDeviceInfo(self):
    data = {}
    for name, char in self.deviceInfoFields:
      data[name] = await self.bleDriver.readDeviceInfoCharacteristic(char)
    return data
  def setPassword(self, password):
    # TODO: Store password
    print(f"[s2c] 0xa0 setPassword({password.hex()})")
    pass
  async def setBroadcastId(self):
    broadcastId = bytearray([0x01, 0x23, 0x45, 0x67])
    print(f"[c2s] 0x21 setBroadcastId({broadcastId.hex()})")
    command = bytearray([0x21]) + broadcastId
    await self.sendCommand(command)
  async def setChallenge(self, challenge):
    print(f"[s2c] 0xa1 setChallenge({challenge.hex()})")
    response = util.transtekChallengeResponse(challenge, self.password)
    await self.setChallengeResponse(response)
  async def setChallengeResponse(self, response):
    await asyncio.sleep(BLE_RESPONSE_DELAY)
    print(f"[c2s] 0x20 setChallengeResponse({response.hex()})")
    command = bytearray([0x20]) + response
    await self.sendCommand(command)
  async def setTime(self):
    await asyncio.sleep(BLE_RESPONSE_DELAY)
    timestampBytes = util.transtekCurrentTimestamp()
    print(f"[c2s] 0x02 setTime({timestampBytes.hex()})")
    command = bytearray([0x02]) + timestampBytes
    await self.sendCommand(command)
    #await self.setWaitingForData()
  async def setWaitingForData(self):
    await asyncio.sleep(BLE_RESPONSE_DELAY)
    print("[c2s] 0x22 setClientWaitingForData()")
    await self.sendCommand(bytearray([0x22]))
  async def sendCommand(self, commandBytes):
    print(f"[c2s] {commandBytes.hex()}")
    await self.bleDriver.writeCommand(commandBytes)
