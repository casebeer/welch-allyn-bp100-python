
import random

from surebp.util import (
    transtekChallengeResponse,
    transtekChallengeResponseInt,
)

def testTranstekChallengeResponse():
    testVectors = [
        (random.randbytes(4).hex(), random.randbytes(4).hex(), None),
        ('ffae2021', '05b67a22', 'fa185a03'),
        ('9316ca61', '596e62e8', 'ca78a889'),
        ('cfd81631', '5e186ca4', '91c07a95'),
    ]
    testVectorBytes = [
        [bytes.fromhex(hexString) if hexString is not None else None for hexString in tv]
        for tv in testVectors
    ]
    for password, challenge, response in testVectorBytes:

        # test that the two methods of computing a challenge reponse match each other
        # one applies bitwise operators to bytearrays one byte at a time
        # one uses struct.pack/unpack to load data into ints and uses bitwise operators on the ints
        assert transtekChallengeResponse(challenge, password) == transtekChallengeResponseInt(challenge, password)

        # if the test vector contains an expected response, confirm that the (bytearray-bytewise)
        # generated response matches the expected response
        if response is not None:
            assert transtekChallengeResponse(challenge, password) == response
