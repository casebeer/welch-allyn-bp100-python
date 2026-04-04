
import datetime
import struct
from dataclasses import dataclass

from .util import convertTimestampToDatetime


@dataclass
class BpData:
    systolic: int
    diastolic: int
    timestamp: datetime.datetime
    heartrate: int
    motionDetected: bool
    irregularHeartbeat: bool
    deviceBatteryOk: bool

    @classmethod
    def fromBpData(cls, data: bytes | bytearray):
        [header, systolic, diastolic, map_, timestamp, heartrate, _, bpFlags, _, deviceFlags] =\
            struct.unpack('<BHHHIHBBBB', data)
        return cls(
            systolic=systolic,
            diastolic=diastolic,
            timestamp=convertTimestampToDatetime(timestamp),
            heartrate=heartrate,
            motionDetected=((bpFlags & 0x01) == 1),
            irregularHeartbeat=(((bpFlags >> 2) & 0x01) == 1),
            deviceBatteryOk=((deviceFlags & 0x01) == 1),
        )
