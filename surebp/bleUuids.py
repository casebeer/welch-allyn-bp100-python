
DEVICE_INFO_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"

MODEL_NUMBER_CHAR = "00002a24-0000-1000-8000-00805f9b34fb"
SERIAL_NUMBER_CHAR = "00002a25-0000-1000-8000-00805f9b34fb"
FIRMWARE_REVISION_CHAR = "00002a26-0000-1000-8000-00805f9b34fb"
HARDWARE_REVISION_CHAR = "00002a27-0000-1000-8000-00805f9b34fb"
SOFTWARE_REVISION_CHAR = "00002a28-0000-1000-8000-00805f9b34fb"
MANUFACTURER_NAME_CHAR = "00002a29-0000-1000-8000-00805f9b34fb"

# Transtek services and characteristics

# Transtek BP service and its characteristics
TRANSTEK_BP_SERVICE = "7809"
TRANSTEK_BP_SERVICE = "00007809-0000-1000-8000-00805f9b34fb"

TRANSTEK_BP_DATA_INDICATE_CHAR = "00008a91-0000-1000-8000-00805f9b34fb"
TRANSTEK_BP_DATA_INDICATE_CHAR = "8a91"

TRANSTEK_BP_DATA_READ_CHAR = "00008a90-0000-1000-8000-00805f9b34fb" # seen but unused in hci logs
TRANSTEK_BP_DATA_NOTIFY_CHAR = "00008a92-0000-1000-8000-00805f9b34fb" # seen but unused in hci logs

TRANSTEK_C2S_COMMAND_CHAR = "00008a81-0000-1000-8000-00805f9b34fb"
TRANSTEK_C2S_COMMAND_CHAR = "8a81"

TRANSTEK_S2C_COMMAND_INDICATE_CHAR = "00008a82-0000-1000-8000-00805f9b34fb"
TRANSTEK_S2C_COMMAND_INDICATE_CHAR = "8a82"

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
