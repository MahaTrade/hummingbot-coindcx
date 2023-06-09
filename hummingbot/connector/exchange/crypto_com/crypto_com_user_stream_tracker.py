import logging
from typing import Optional

import aiohttp

from hummingbot.connector.exchange.crypto_com.crypto_com_api_user_stream_data_source import (
    CryptoComAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_constants import EXCHANGE_NAME
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class CryptoComUserStreamTracker(UserStreamTracker):
    _cbpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self,
                 crypto_com_auth: Optional[CryptoComAuth] = None,
                 shared_client: Optional[aiohttp.ClientSession] = None,
                 ):
        self._crypto_com_auth: CryptoComAuth = crypto_com_auth
        self._shared_client = shared_client or aiohttp.ClientSession()
        super().__init__(data_source=CryptoComAPIUserStreamDataSource(
            crypto_com_auth=self._crypto_com_auth,
            shared_client=self._shared_client
        ))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        *required
        Initializes a user stream data source (user specific order diffs from live socket stream)
        :return: OrderBookTrackerDataSource
        """
        if not self._data_source:
            self._data_source = CryptoComAPIUserStreamDataSource(
                crypto_com_auth=self._crypto_com_auth,
                shared_client=self._shared_client
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return EXCHANGE_NAME

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
