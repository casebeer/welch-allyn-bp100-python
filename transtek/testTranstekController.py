import logging
logging.basicConfig(level=logging.DEBUG)

import asyncio
import pytest

from .TranstekController import TranstekController
from .MockTranstekBleDriver import MockTranstekBleDriver

pytest_plugins = ('pytest_asyncio',)

@pytest.mark.asyncio
async def testTranstekController():
  transtekController = TranstekController(
    driver=MockTranstekBleDriver(),
    password=bytearray([ 0xaa, 0xbb, 0xcc, 0xdd ])
  )
  await transtekController.initialize()

async def main():
  await testTranstekController()

if __name__ == '__main__':
  asyncio.run(main())
