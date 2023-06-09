import logging
from typing import List, Optional

from hummingbot.connector.exchange.blocktane.blocktane_api_user_stream_data_source import (
    BlocktaneAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.blocktane.blocktane_auth import BlocktaneAuth
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class BlocktaneUserStreamTracker(UserStreamTracker):
    _bust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self,
                 blocktane_auth: Optional[BlocktaneAuth] = None,
                 trading_pairs=None):
        self._blocktane_auth: BlocktaneAuth = blocktane_auth
        self._trading_pairs: List[str] = trading_pairs
        super().__init__(data_source=BlocktaneAPIUserStreamDataSource(
            blocktane_auth=self._blocktane_auth,
            trading_pairs=self._trading_pairs))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = BlocktaneAPIUserStreamDataSource(
                blocktane_auth=self._blocktane_auth, trading_pairs=self._trading_pairs
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "blocktane"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
