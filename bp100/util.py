'''
Utility functions to handle Transtek BLE protocol data
'''

import datetime
import time
import struct
import functools
import random

def transtekChallengeResponse(challenge: bytearray, password: bytearray) -> bytearray:
    return bytearray([p ^ c for p, c in zip(password, challenge)])

def transtekChallengeResponseInt(challenge: bytearray, password: bytearray) -> bytearray:
    challengeInt, = struct.unpack('<I', challenge)
    passwordInt, = struct.unpack('<I', password)
    responseInt = challengeInt ^ passwordInt
    return bytearray(struct.pack('<I', responseInt))

def verifyChallengeResponse(password: bytearray, challenge: bytearray, response: bytearray) -> bool:
    # challenge ^ response ^ password should be all zero bytes
    validate = [ p ^ c ^ r for p, c, r in zip(password, challenge, response) ]
    valid = (functools.reduce(lambda a, b: a + b, validate) == 0)
    return valid


def parseTranstekTimestamp(timestampBytes):
  timestampSeconds, = struct.unpack('<I', timestampBytes)
  return convertTimestampToDatetime(timestampSeconds)


def convertTimestampToDatetime(timestampSeconds):
  epoch = datetime.datetime(2010, 1, 1, 0, 0, 0)
  # see dstRemovalCorrection() for explanation
  return epoch + datetime.timedelta(days=timestampSeconds / 24 / 60 / 60) + dstRemovalCorrection()


def transtekCurrentTimestamp():
    return transtekTimestamp(datetime.datetime.now())


def transtekTimestamp(dt):
    # Compute Transtek timestamp as seconds since 2010-01-01 00:00:00
    epoch = datetime.datetime(2010, 1, 1, 0, 0, 0)

    # see dstRemovalCorrection() for explanation
    timestamp: datetime.timedelta = dt - epoch - dstRemovalCorrection()
    timestampSeconds = int(timestamp.total_seconds())
    timestampBytes = struct.pack('<I', timestampSeconds)
    return timestampBytes


def dstRemovalCorrection():
    # For some reason, the Welch Allyn Home app sends and interprets timestamps as
    # local time without DST. Not clear we need to accomodate this if we're the device's only
    # client, but for compatibility, we'll adjust our timestamps here.
    isDst = time.localtime().tm_isdst
    dstRemovalCorrection = datetime.timedelta(seconds=3600 if isDst else 0)
    return dstRemovalCorrection
