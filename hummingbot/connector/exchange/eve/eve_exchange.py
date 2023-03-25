from typing import List, Optional

from hummingbot.connector.exchange.alpha_point.alpha_point_exchange import AlphaPointExchange
from hummingbot.connector.exchange.eve import eve_constants as CONSTANTS
from hummingbot.connector.exchange.eve.eve_web_utils import EveURLCreator


class EveExchange(AlphaPointExchange):
    def __init__(
        self,
        eve_api_key: str,
        eve_secret_key: str,
        eve_user_id: int,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        url_creator: Optional[EveURLCreator] = None,
    ):
        url_creator = url_creator or EveURLCreator(
            rest_base_url=CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_VARIANT],
            ws_base_url=CONSTANTS.WS_URLS[CONSTANTS.DEFAULT_VARIANT],
        )
        super().__init__(
            api_key=eve_api_key,
            secret_key=eve_secret_key,
            user_id=eve_user_id,
            trading_pairs=trading_pairs,
            trading_required=trading_required,
            url_creator=url_creator,
        )

    @property
    def name(self) -> str:
        return "eve"

    @property
    def oms_id(self) -> int:
        return CONSTANTS.OMS_ID
