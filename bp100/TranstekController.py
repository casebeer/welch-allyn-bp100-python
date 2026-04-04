
import logging

from .bleUuids import (
    DeviceInfoCharacteristics,
)
from .password import PasswordStrategy
from .TranstekBleDriver import TranstekBleDriver, BleWriteError

import pprint
import asyncio
import enum

from . import util
from .model import BpData

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

    def __init__(self, bleDriver: TranstekBleDriver, broadcastId=None, password=None):
        self.deviceInfo = {}
        self.bleDriver: TranstekBleDriver = bleDriver

        # byte sequence len 4 used to set BLE advertised name during pairing
        # broadcastId is ONLY used during pairing to set the device's advertising name
        self.broadcastId: bytes[4] = broadcastId if broadcastId is not None \
                                        else self.defaultBroadcastId

        # If password is None, password will default to MAC-based password.
        # If device is in paring mode, any password set here will be overwritten by the password
        # provided by the device.
        self.password = password

        if self.password is not None:
            self.passwordStrategy = PasswordStrategy.SPECIFIED_PASSWORD
        else:
            self.passwordStrategy = PasswordStrategy.defaultGuess()

        self.finished = asyncio.Event()
        self.bpDataQueue = asyncio.Queue()

        self.state = BpStates.INIT

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        '''Make sure self.deviceInfo gets copy of password any time it's set.'''
        self._password = value
        try:
            self.deviceInfo['password'] = value.hex() if value is not None else None
        except:
            logger.warn(f"Attempted to set invalid password '{value}' that is not 4 bytes.")
            self.deviceInfo['password'] = None

    async def initialize(self):
        logger.debug(f"Connecting to BP device using password strategy {self.passwordStrategy}...")

        await self.bleDriver.connect()

        self.deviceInfo.update(await self.getDeviceInfo())

        if type(self.deviceInfo.get(DeviceInfoCharacteristics.SYSTEM_ID.name, None)) == bytearray:
            # convert system_id to hex
            self.deviceInfo[DeviceInfoCharacteristics.SYSTEM_ID.name] = \
                self.deviceInfo[DeviceInfoCharacteristics.SYSTEM_ID.name].hex()

        if self.passwordStrategy.isMacBased():
            self.setPasswordFromSn()

        logger.debug(pprint.pformat(self.deviceInfo))

        await self.bleDriver.subscribeToBpData(self.bpDataHandler)

        # Once we've subscribed to the commands inidication characteristic, the Transtek protocol
        # will begin when the device sends us an 0xa1 "setChallenge" command inidication.
        await self.bleDriver.subscribeToCommands(self.commandHandler)

        self.bleDriver.setDisconnectCallback(self.disconnectHandler)

        logger.debug("BLE indications configured.")

    @property
    def serialNumber(self):
        return self.deviceInfo[DeviceInfoCharacteristics.SERIAL_NUMBER.name]

    def setPasswordFromSn(self):
        self.password = self.passwordStrategy.passwordFromSn(self.serialNumber)
        logger.debug(f"Setting password to '{self.password.hex()}' "
                     f"from serial number using {self.passwordStrategy}")

    def disconnectHandler(self):
        if self.state == BpStates.AUTHENTICATING:
            # let reconnectAfterAuthError handle cleaning up (or not)
            logger.debug(f"BLE driver disconnected while {self.state}. Letting reconnectAfterAuthError continue...")
        else:
            logger.debug(f"BLE driver disconnected with no auth retry needed, cleaning up and exiting...")
            self.finished.set()
            self.close()

    async def reconnectAfterAuthError(self):
        logger.debug("Attempting to reconnect BLE driver to try another password...")
        # clean up old connection
        await self.bleDriver.disconnect()

        # reset driver to default settings
        self.bleDriver.reset()

        # advance to next password strategy
        logger.debug(f"Moving to next strategy after {self.passwordStrategy} before reconnecting...")
        self.passwordStrategy = self.passwordStrategy.next()
        if self.passwordStrategy == PasswordStrategy.FAILED:
            logger.error("All password strategies exhausted. Failed to authenticate.")
            self.finished.set()
            return

        logger.debug("Reconnecting...")

        # reconnect
        await self.initialize()

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
                self.state = self.state.transition('pair')
                self.passwordStrategy = PasswordStrategy.PROVIDED_BY_DEVICE

                self.setPassword(data[1:5])
                await self.setBroadcastId()
            case 0xa1:
                self.state = self.state.transition('authenticate')
                await self.setChallenge(data[1:5])

                try:
                    await self.setTime()

                    # notify state machine setTime writeWithResponse has succeeded (and thus our
                    # authentication has been accepted)
                    self.state = self.state.transition('authenticated')
                    logger.info(f"Password '{self.password.hex()}' "
                                f"via {self.passwordStrategy} accepted.")
                except BleWriteError:
                    # if setTime fails, our authentication has likely been rejected
                    logger.error("Write failure after auth, presume password "
                                 f"'{self.password.hex()}' via {self.passwordStrategy} "
                                 "has been rejected")
                    await self.reconnectAfterAuthError()
                    return

                if self.state == BpStates.PAIRED:
                    await self.setWaitingForData()
            case 0x22:
                logger.debug("[s2c] 0x22 deviceWillDisconnect")
                await self.bleDriver.disconnect()
            case _:
                pass

    # TODO: Add state machine update so we can error if we get no BP data
    async def bpDataHandler(self, dataBytes: bytearray):
        bpData = BpData.fromBpData(dataBytes)

        logger.info(f"Got BP data from {bpData.timestamp}")

        self.bpDataQueue.put_nowait(bpData)  # n.b. exception if Queue full

        logger.debug(pprint.pformat(bpData))
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
        '''Wait until this Controller's life cycle is finished'''
        await self.finished.wait()
        self.close()

    async def getDeviceInfo(self):
        data = {}
        for char in DeviceInfoCharacteristics:
            data[char.name] = await self.bleDriver.readDeviceInfoCharacteristic(char.value)
        return data
    def setPassword(self, password):
        logger.info(f"[s2c] 0xa0 setPassword({password.hex()}) "
                    f"Received long term password from device: {password.hex()}")
        if password in PasswordStrategy.generateAllSnPasswords(self.serialNumber):
            logger.info(f"This password matches one of the guessed BLE MAC-address derived "
                         "passwords, so doesn't need to be stored.")
        else:
            logger.warn(f"The long term password {password.hex()} received from the device does "
                        "NOT match any of the BLE MAC-address derived password possibilities,"
                        "so must be stored long-term and sent with any future data requests.")
        self.password = password
    async def setBroadcastId(self):
        logger.debug(f"[c2s] 0x21 setBroadcastId({self.broadcastId.hex()})")
        command = bytearray([0x21]) + self.broadcastId
        await self.sendCommand(command)
    async def setChallenge(self, challenge):
        logger.debug(f"[s2c] 0xa1 setChallenge({challenge.hex()})")
        response = util.transtekChallengeResponse(challenge, self.password)
        logger.debug(f"      Computing challenge response withpassword {self.password.hex()}")
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

class BpStates(enum.Enum):
    INIT = enum.auto()
    PAIRING = enum.auto()
    PAIRED = enum.auto()
    AUTHENTICATING = enum.auto()
    AUTHENTICATED = enum.auto()

    def transition(self, action):
        match self, action:
            case state, 'pair':
                return BpStates.PAIRING
            case BpStates.PAIRING, 'authenticated':
                return BpStates.PAIRED

            case BpStates.INIT, 'authenticate':
                return BpStates.AUTHENTICATING
            case BpStates.AUTHENTICATING, 'authenticated':
                return BpStates.AUTHENTICATED
            case _:
                return self

class AuthenticationError(Exception):
    pass
