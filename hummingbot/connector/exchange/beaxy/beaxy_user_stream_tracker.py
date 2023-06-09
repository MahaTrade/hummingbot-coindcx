import logging
from typing import List, Optional

from hummingbot.connector.exchange.beaxy.beaxy_api_user_stream_data_source import BeaxyAPIUserStreamDataSource
from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather


class BeaxyUserStreamTracker(UserStreamTracker):
    _bxyust_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._bxyust_logger is None:
            cls._bxyust_logger = logging.getLogger(__name__)
        return cls._bxyust_logger

    def __init__(
        self,
        beaxy_auth: BeaxyAuth,
        trading_pairs: Optional[List[str]] = None,
    ):
        self._beaxy_auth = beaxy_auth
        self._trading_pairs: List[str] = trading_pairs or []
        super().__init__(data_source=BeaxyAPIUserStreamDataSource(
            beaxy_auth=self._beaxy_auth,
            trading_pairs=self._trading_pairs))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = BeaxyAPIUserStreamDataSource(
                beaxy_auth=self._beaxy_auth, trading_pairs=self._trading_pairs)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return 'beaxy'

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
