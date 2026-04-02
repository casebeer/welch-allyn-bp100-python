'''
BLE GATT UUID definifitions

n.b. that Python Bleak can have problems matching "short" 16 bit UUIDs, e.g. when passing
     service_uuids to BleakScanner; normalize with normalize_uuid_str() or use the long forms.
'''

from enum import Enum

class GattServices(Enum):
    DEVICE_INFO = "180a"  # Generic BLE/GATT
    TRANSTEK_BP = "00007809-0000-1000-8000-00805f9b34fb" # long form for BleakScanner compatibility

class DeviceInfoCharacteristics(Enum):
    '''
    Characteristic UUIDs for the BLE GATT Device Info service

    n.b. specified as "short" 16 bit UUIDs; these can all be converted to full UUIDs by replacing
         bytes two and three of the template UUID "0000xxxx-0000-1000-8000-00805f9b34fb" with the
         short UUID.
    '''
    SYSTEM_ID = "2a23"
    MODEL_NUMBER = "2a24"
    SERIAL_NUMBER = "2a25"
    FIRMWARE_REVISION = "2a26"
    HARDWARE_REVISION = "2a27"
    SOFTWARE_REVISION = "2a28"
    MANUFACTURER_NAME = "2a29"

class TranstekCharacteristics(Enum):
    # c2s and s2c command write and "read" characterisitics
    # Used to set time, challenge/response auth, etc.
    C2S_COMMAND = "8a81"
    S2C_COMMAND_INDICATE = "8a82"

    # Used to receive BP data from the device
    BP_DATA_INDICATE = "8a91"

    BP_DATA_READ = "8a90" # seen but unused in hci logs
    BP_DATA_NOTIFY = "8a92" # seen but unused in hci logs

# Seen on device:
#
# 0x7809 Transtek BP Service
#   0x8a90 ??? (read) (untested)
#   0x8a91 BP Data (indicate)
#   0x8a92 BP Data (notify) (doesn't work)
#
#   0x8a81 C2S Command (write)
#   0x8a82 S2C Command (indicate)
#
# 0x180a Device Info Service
#   0x2a23 System ID (not retreived) (causes error in enumeration from Android app client)
#   0x2a24 Model number
#   0x2a25 Serial number
#   0x2a26 Firmware revision
#   0x2a27 Hardware revision
#   0x2a28 Software revision
#   0x2a29 Manufacturer name
