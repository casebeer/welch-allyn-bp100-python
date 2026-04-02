
from bp100.util import (
    convertTimestampToDatetime,
    verifyChallengeResponse,
)

from bp100.bleUuids import (
    DeviceInfoCharacteristics,
)

import asyncio
import datetime
import random
import struct

MOCK_SERIAL_NUMBER = "8899AABBCCDD" # last 8 chars used as password
MOCK_DEVICE_INFO = {
    DeviceInfoCharacteristics.SERIAL_NUMBER.value: MOCK_SERIAL_NUMBER,
}
MOCK_DEVICE_PASSWORD = bytearray([ 0xaa, 0xbb, 0xcc, 0xdd ])
MOCK_BP_DATA = bytearray([0x34, 0xff, 0x00, 0xfe, 0x00, 0x00, 0x00, 0xff, 0xff,
                          0xff, 0x00, 0xfd, 0x00, 0x00, 0x00, 0x00, 0x01 ])

class MockTranstekBleDriver(object):
    def __init__(self, client=None):
        self.mockServer = MockTranstekBpMonitor(disconnectHandler=self.disconnect)
        self.finished = asyncio.Event()
        self.disconnectCallback = None
    async def connect(self):
        return
    def setDisconnectCallback(self, handler):
        self.disconnectCallback = handler
    async def subscribeToCommands(self, handler):
        await self.mockServer.subscribeToCommands(handler)
    async def subscribeToBpData(self, handler):
        self.mockServer.subscribeToBpData(handler)
    async def readDeviceInfoCharacteristic(self, char):
        return self.mockServer.readDeviceInfoCharacteristic(char)
    async def writeCommand(self, commandBytes):
        await self.mockServer.c2sCommand(commandBytes)
    async def disconnect(self):
        self.finished.set()
        if self.disconnectCallback is not None:
            self.disconnectCallback()
    async def join(self):
        await self.finished.wait()

class MockTranstekBpMonitor(object):
    def __init__(self, disconnectHandler):
        self.clientReadyForData = asyncio.Event()
        self.password = MOCK_DEVICE_PASSWORD
        self.disconnectHandler = disconnectHandler
    async def subscribeToCommands(self, handler):
        self.commandHandler = handler
        await self.setChallenge()
    def subscribeToBpData(self, handler):
        self.bpDataHandler = handler
    def readDeviceInfoCharacteristic(self, char):
        return MOCK_DEVICE_INFO.get(char, "NOT IMPLEMENTED")
    async def c2sCommand(self, commandBytes):
        print("[mock][c2s] {}".format(commandBytes.hex()))
        match commandBytes[0]:
            case 0x20:
                await self.acceptChallengeResponse(commandBytes[1:5])
            case 0x21:
                self.acceptBroadcastId(commandBytes[1:5])
            case 0x22:
                print("[mock][c2s] 0x22 clientWaitingForData")
                self.clientReadyForData.set()
            case 0x02:
                await self.acceptTime(commandBytes[1:5])
            case _:
                pass
    def acceptBroadcastId(self, broadcastIdBytes):
        print("[mock][c2s] 0x21 setBroadcastId({})".format(broadcastIdBytes.hex()))
    async def setChallenge(self):
        self.challenge = bytearray(random.randbytes(4))
        await self.s2cCommand(bytearray([0xa1]) + self.challenge)
    async def acceptChallengeResponse(self, responseBytes):
        print("[mock][c2s] 0x20 setChallengeResponse({})".format(responseBytes.hex()))
        print("[mock]           password is  {}".format(self.password.hex()))
        print("[mock]           challenge is {}".format(self.challenge.hex()))
        valid = verifyChallengeResponse(self.password, self.challenge, responseBytes)
        if valid:
            print("[mock]           challenge-response accepted")
        else:
            print("[mock]           challenge-response FAILED")
        assert valid

    async def acceptTime(self, timestampBytes):
        timestampSeconds, = struct.unpack('<I', timestampBytes)
        print("[mock][c2s] 0x02 setTime({})".format(timestampSeconds))
        actualTime = datetime.datetime.now()
        providedTime = convertTimestampToDatetime(timestampSeconds)
        print("[mock]           time set to {}".format(providedTime))
        print("[mock]           actual time {}".format(actualTime))

        # TODO: ensure all time is frozen during test
        assert abs((providedTime - actualTime).total_seconds()) < 2

        await self.sendAllBpData()

    async def sendAllBpData(self):
        for i in range(3):
            self.clientReadyForData.clear()
            await self.s2cBpData(MOCK_BP_DATA)
            await self.clientReadyForData.wait()

        await self.disconnect()

    async def disconnect(self):
        await self.disconnectHandler()
    async def s2cCommand(self, commandBytes):
        print("[mock][s2c] {}".format(commandBytes.hex()))
        await self.commandHandler(commandBytes)

    async def s2cBpData(self, bpDataBytes):
        print("[mock][s2c][bpData] {}".format(bpDataBytes.hex()))
        await self.bpDataHandler(bpDataBytes)
