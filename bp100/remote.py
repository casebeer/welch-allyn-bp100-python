
import asyncio
import habluetooth
import logging

from bleak_esphome import APIConnectionManager, ESPHomeDeviceConfig
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

PROXY_CONNECTION_TIMEOUT = 5


@asynccontextmanager
async def bleakEsphomeProxies(
        proxies: list[ESPHomeDeviceConfig],
        timeout: int = PROXY_CONNECTION_TIMEOUT,
        ):
    connections = [APIConnectionManager(device) for device in proxies]
    try:
        # async_setup() monkeypatches bleak.BleakScanner, bleak.BleakClient,
        #   bleak_retry_connector.BleakClient, and
        #   bleak_retry_connector.BleakClientWithServiceCache
        # WARNING side effects outside context manager
        await habluetooth.BluetoothManager().async_setup()

        await asyncio.wait(
            (asyncio.create_task(conn.start()) for conn in connections),
            timeout=timeout,
        )

        yield connections
    finally:
        await asyncio.gather(*(conn.stop() for conn in connections))
        habluetooth.BluetoothManager().async_stop()  # n.b. not actually async


def proxyStringToConfig(proxyString: str) -> ESPHomeDeviceConfig:
    '''Convert colon separates address:noise_psk pairs'''
    # rsplit only on final : since we know Base64 Noise PSK can't contain colons
    address, noisePsk = proxyString.rsplit(':')
    return {
        'address': address,
        'noise_psk': noisePsk,
    }
