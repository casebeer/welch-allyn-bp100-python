
from .util import (
    convertTimestampToDatetime,
    verifyChallengeResponse,
)

import asyncio
import datetime
import random
import struct

class MockTranstekBleDriver(object):
    def __init__(self, client=None):
        self.mockServer = MockTranstekBpMonitor()
    async def subscribeToCommands(self, handler):
        await self.mockServer.subscribeToCommands(handler)
    async def subscribeToBpData(self, handler):
        self.mockServer.subscribeToBpData(handler)
    async def readDeviceInfoCharacteristic(self, char):
        return "NOT IMPLEMENTED"
    async def writeCommand(self, commandBytes):
        await self.mockServer.c2sCommand(commandBytes)

class MockTranstekBpMonitor(object):
    def __init__(self):
        self.clientReadyForData = asyncio.Event()
        self.password = bytearray([ 0xaa, 0xbb, 0xcc, 0xdd ])
    async def subscribeToCommands(self, handler):
        self.commandHandler = handler
        await self.setChallenge()
    def subscribeToBpData(self, handler):
        self.bpDataHandler = handler
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
    async def acceptTime(self, timestampBytes):
        timestampSeconds, = struct.unpack('<I', timestampBytes)
        print("[mock][c2s] 0x02 setTime({})".format(timestampSeconds))
        actualTime = datetime.datetime.now()
        providedTime = convertTimestampToDatetime(timestampSeconds)
        print("[mock]           time set to {}".format(providedTime))
        print("[mock]           actual time {}".format(actualTime))
        await self.sendAllBpData()
    async def sendAllBpData(self):
        for i in range(3):
            self.clientReadyForData.clear()
            await self.s2cBpData(bytearray([0x34, 0xff, 0x00, 0xfe, 0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0x00, 0xfd, 0x00, 0x00, 0x00, 0x00, 0x01 ]))
            await self.clientReadyForData.wait()
    async def s2cCommand(self, commandBytes):
        print("[mock][s2c] {}".format(commandBytes.hex()))
        await self.commandHandler(commandBytes)
    async def s2cBpData(self, bpDataBytes):
        print("[mock][s2c][bpData] {}".format(bpDataBytes.hex()))
        await self.bpDataHandler(bpDataBytes)
