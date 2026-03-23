
import logging

from .bleUuids import (
    DeviceInfoCharacteristics,
)

from .TranstekBleDriver import TranstekBleDriver

import pprint
import asyncio

from . import util

logger = logging.getLogger(__name__)
BLE_RESPONSE_DELAY = 0.01 # slow down messages sent to GATT server

'''
# TranstekController

Coordinate BLE indication subscriptions and writes for Transtek BLE BP monitor.

Transtek (OEM for Welch Allyn BP100 models 1500 and 1700) BLE blood pressure monitors
exchange commands with the client via writes to a client-to-sever characteristic and indicate
subscriptions to a server-to-client characteristic.

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

The "password" appears to be the last 8 hex chars of the reported device info serial number,
interpreted as four bytes. This is also the byte-wise-reversed FIRST four bytes of the MAC address.

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
    defaultBroadcastId = bytearray([0x01, 0x23, 0x45, 0x67])

    def __init__(self, bleDriver, broadcastId=None):
        self.bleDriver = bleDriver

        # byte sequence len 4 used to set BLE advertised name during pairing
        self.broadcastId = broadcastId if broadcastId is not None else self.defaultBroadcastId

        self.password = None # will set password after readDeviceInfo or receipt of 0xa0 setPassword

        self.bpDataQueue = asyncio.Queue()

    async def onFinished(self):
        await self.bleDriver.finished.wait()
        self.close()

    async def initialize(self):
        logger.debug("Initializing Transtek BLE client...")

        await self.bleDriver.connect()
        asyncio.create_task(self.onFinished())  # cleanup callback when bleClient is finished

        self.deviceInfo = await self.getDeviceInfo()

        # Set password using last 8 hex chars of reported SERIAL_NUMBER
        # n.b. the reported serial number is just the device's BLE MAC address reversed octet-wise,
        # i.e. 11:22:33:44:55:66 -> 66:55:44:33:22:11, so the password is also the first four bytes
        # of the MAC address, byte-wise reversed.
        serialNumber = self.deviceInfo[DeviceInfoCharacteristics.SERIAL_NUMBER.name]
        self.password = bytes.fromhex(serialNumber[-8:])

        logger.debug(pprint.pformat(self.deviceInfo))

        await self.bleDriver.subscribeToBpData(self.bpDataHandler)

        # Once we've subscribed to the commands inidication characteristic, the Transtek protocol
        # will begin when the device sends us an 0xa1 "setChallenge" command inidication.
        await self.bleDriver.subscribeToCommands(self.commandHandler)

        logger.debug("BLE indications configured.")

    async def commandHandler(self, data: bytearray):
        logger.debug(f"[s2c] {data.hex()}")
        match data[0]:
            case 0xa0:
                # n.b. we only receive this when connecting to a device for the first time
                #      Generally, we're assuming the password is the last 8 hex chars of the
                #      reported serial number, but if we get this a0 command, the password it
                #      provides should override that assumption. Additionally, if the password
                #      provided does not match the last 8 hex chars of the SN, swe should store it
                #      long term and use that value instead of the presumed SN/MAC based password.
                self.setPassword(data[1:5])
                await self.setBroadcastId()
            case 0xa1:
                await self.setChallenge(data[1:5])
                await self.setTime()
                # TODO: if pairing, then self.setWaitingForData()
                await self.setWaitingForData()
            case 0x22:
                logger.debug("[s2c] 0x22 deviceWillDisconnect")
                await self.bleDriver.disconnect()
            case _:
                pass

    async def bpDataHandler(self, dataBytes: bytearray):
        data = util.parseBpData(dataBytes)

        self.bpDataQueue.put_nowait(data) # n.b. exception if Queue full

        logger.debug(pprint.pformat(data))
        await self.setWaitingForData()

    def close(self):
        '''Cleanup TranstekController after connection is done.'''
        # add terminiation sigil to queue
        self.bpDataQueue.put_nowait(None)

    async def bpData(self):
        '''Async generator returning BP data'''
        while True:
            data = await self.bpDataQueue.get()

            if data is None:
                # sigil placed by our close() method, clean up and end
                self.bpDataQueue.task_done()
                break

            yield data
            self.bpDataQueue.task_done()

    async def join(self):
        '''Wait until this Controller's life cycle is finished (as determined by its bleDriver)'''
        await self.bleDriver.join()
        self.close()

    async def getDeviceInfo(self):
        data = {}
        for char in DeviceInfoCharacteristics:
            data[char.name] = await self.bleDriver.readDeviceInfoCharacteristic(char.value)
        return data
    def setPassword(self, password):
        logger.debug(f"[s2c] 0xa0 setPassword({password.hex()})")
        logger.info(f"Received long term password from device: {password.hex()}\n")
        if password == self.password:
            logger.info("This password matches the presumed BLE MAC-address derived password {self.password.hex()}, "
                        "so doesn't need to be stored.")
        else:
            logger.warn(f"The long term password {password.hex()} received from the device does "
                        "NOT match the normal BLE MAC-address derived password "
                        f"{self.password.hex()}. The device-provided password must be stored "
                        "long-term and sent with any future data requests.")
            self.password = password
    async def setBroadcastId(self):
        logger.debug(f"[c2s] 0x21 setBroadcastId({self.broadcastId.hex()})")
        command = bytearray([0x21]) + self.broadcastId
        await self.sendCommand(command)
    async def setChallenge(self, challenge):
        logger.debug(f"[s2c] 0xa1 setChallenge({challenge.hex()})")
        response = util.transtekChallengeResponse(challenge, self.password)
        await self.setChallengeResponse(response)
    async def setChallengeResponse(self, response):
        await asyncio.sleep(BLE_RESPONSE_DELAY)
        logger.debug(f"[c2s] 0x20 setChallengeResponse({response.hex()})")
        command = bytearray([0x20]) + response
        await self.sendCommand(command)
    async def setTime(self):
        await asyncio.sleep(BLE_RESPONSE_DELAY)
        timestampBytes = util.transtekCurrentTimestamp()
        logger.debug(f"[c2s] 0x02 setTime({timestampBytes.hex()})")
        command = bytearray([0x02]) + timestampBytes
        await self.sendCommand(command)
        #await self.setWaitingForData()
    async def setWaitingForData(self):
        await asyncio.sleep(BLE_RESPONSE_DELAY)
        logger.debug("[c2s] 0x22 setClientWaitingForData()")
        await self.sendCommand(bytearray([0x22]))
    async def sendCommand(self, commandBytes):
        logger.debug(f"[c2s] {commandBytes.hex()}")
        await self.bleDriver.writeCommand(commandBytes)
