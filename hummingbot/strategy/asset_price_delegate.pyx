from decimal import Decimal
from typing import List

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.common import PriceType

cdef class AssetPriceDelegate:
    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def get_mid_price(self) -> Decimal:
        return self.c_get_mid_price()
    # ---------------------------------------------------------------

    def get_price_by_type(self, price_type: PriceType) -> Decimal:
        raise NotImplementedError

    cdef object c_get_mid_price(self):
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def market(self) -> ExchangeBase:
        raise NotImplementedError

    @property
    def all_markets(self) -> List[ExchangeBase]:
        return [self.market]
