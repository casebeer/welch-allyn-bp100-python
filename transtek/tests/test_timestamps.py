
import datetime

from transtek.util import (
    parseTranstekTimestamp,
    transtekTimestamp,
)

# n.b. these test vectors were all captured during DST, so appear to
# be one hour off from the presumed "seconds since 2010-01-01 epoch"
# timestamp definition – timestamps seem to be in local standard time
# regardless of time of year.
timestampTestVectors = [
    ("6e80071d", datetime.datetime(2025, 6, 7, 23, 21, 34)),
    ("ef8b071d", datetime.datetime(2025, 6, 8,    0, 10, 39)),
    ("5987071d", datetime.datetime(2025, 6, 7, 23, 51,    5)),
    ("c386071d", datetime.datetime(2025, 6, 7, 23, 48, 35)),
    ("207c071d", datetime.datetime(2025, 6, 7, 23,    3, 12)),
    ("aa7b071d", datetime.datetime(2025, 6, 7, 23,    1, 14)),
    ("be6c071d", datetime.datetime(2025, 6, 7, 21, 57, 34)),
    ("576c071d", datetime.datetime(2025, 6, 7, 21, 55, 51)),
    ("4869071d", datetime.datetime(2025, 6, 7, 21, 42, 48)),
    ("0f77071d", datetime.datetime(2025, 6, 7, 22, 41, 35)),
    ("c576071d", datetime.datetime(2025, 6, 7, 22, 40, 21)),
]


def testParseTranstekTimestamp():
    for ts, dt in timestampTestVectors:
        #printTs(ts)
        #print(parseTranstekTimestamp(bytearray(bytes.fromhex(ts))) - dt)
        assert parseTranstekTimestamp(bytearray(bytes.fromhex(ts))) == dt


def testTranstekTimestamp():
    for ts, dt in timestampTestVectors:
        assert transtekTimestamp(dt).hex() == ts


def main():
    testParseTranstekTimestamp()
    testTestTranstekTimestamp()

if __name__ == '__main__':
    main()
