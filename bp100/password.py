import enum

class PasswordStrategy(enum.Enum):
    '''
    State machine for guessing SN/MAC address based passwords

    BT MAC (i.e. BDADDR) based passwords can be computed from the GATT device info reported serial
    number in four different ways.

    Note that we use the GATT device info serial number to get the BDADDR since the BDADDR is not
    exposed to us on MacOS for privacy reasons.

    The GATT serial number can be either the big-endian (normal BDADDR display format) BDADDR or the
    little-endian (normal BDADDR wire format) BDADDR.

    The password is based on the wire format little-endian BDADDR. It can be either the first or
    last four bytes of the little-endian BDADDR.

    This gives four combinations to try, to be tried in order:

        LE s/n, last four of LE BDADDR - seen on device with removable BP cuff and "Ver. A" on rear sticker
        BE s/n, first four of LE BDADDR - seen on device with non-removable cuff and "Ver. B" on sticker
        LE s/n, first four of LE BDADDR
        BE s/n, last four of LE BDADDR
    '''
    # enum values are booleans (macBasedGuess, beSerialNumber, leBdAddrStart) specifying strategy
    SPECIFIED_PASSWORD = (False, 1, None)
    PROVIDED_BY_DEVICE = (False, 2, None) # during pairing

    LE_SN_LE_BDADDR_END = (True, False, False) # Ver. A device (removable cuff)
    BE_SN_LE_BDADDR_START = (True, True, True) # Ver. B device (non-removable cuff)

    LE_SN_LE_BDADDR_START = (True, False, True) # not observed
    BE_SN_LE_BDADDR_END = (True, True, False) # not observed

    FAILED = (False, -1, None)

    @classmethod
    def defaultGuess(cls):
        return cls.LE_SN_LE_BDADDR_END # seen on Ver. A device

    def next(self):
        '''Advance to next strategy'''
        if not self.isMacBased():
            # only MAC-based guessing strategies can be advanced
            return self.__class__.FAILED

        members = list(self.__class__)
        nextIndex = members.index(self) + 1

        if nextIndex >= len(members):
            return self.__class__.FAILED

        return members[nextIndex]

    def isMacBased(self):
        macBasedGuess, _, _ = self.value
        return macBasedGuess

    def passwordFromSn(self, serialNumber):
        _, bigEndianSn, leBdAddrStart = self.value

        if not self.isMacBased():
            # password strategy is not a MAC-based guessing strategy, fail
            raise Exception(f"{self} cannot be used to generate a password from a serial number")

        return self.passwordFromSnAndStrategy(serialNumber, bigEndianSn, leBdAddrStart)

    @staticmethod
    def passwordFromSnAndStrategy(serialNumber, bigEndianSn, leBdAddrStart):
        snBytes = bytes.fromhex(serialNumber)

        # passwords are based on the little-endian wire-format of the bdAddr
        # bdAddrs are ALWAYS written/displayed in big-endian (e.g. on the sticker on the device)
        # the "serial number" reported by GATT device info is sometimes the big-endian display value
        # of the bdAddr, and sometimes the little-endian wire value of the bdAddr
        if bigEndianSn:
            leBdAddr = snBytes[::-1]  # reverse bytes
        else:
            leBdAddr = snBytes

        # password is either start or end of the little-endian wire format bdAddr
        if leBdAddrStart:
            password = leBdAddr[:4]  # first four bytes
        else:
            password = leBdAddr[-4:]  # last four bytes

        return password

    @classmethod
    def generateAllSnPasswords(cls, serialNumber):
        '''Generate MAC based passwords using all strategies for provided serial number'''
        results = []
        for beSn in (True, False):
            for addrStart in (False, True):
                results.append(cls.passwordFromSnAndStrategy(serialNumber, beSn, addrStart))
        return results
