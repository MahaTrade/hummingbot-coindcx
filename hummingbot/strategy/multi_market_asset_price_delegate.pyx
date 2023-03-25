from typing import List, Tuple
from decimal import Decimal

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import PriceType
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate, \
    OrderBookInverseAssetPriceDelegate
from hummingbot.strategy.asset_price_delegate cimport AssetPriceDelegate


cdef class MultiMarketAssetPriceDelegate(AssetPriceDelegate):

    def __init__(self, price_delegates: List[OrderBookAssetPriceDelegate]):
        super().__init__()
        self._price_delegates = price_delegates

    @classmethod
    def for_markets(cls, connectors_and_pairs: List[Tuple[ExchangeBase, str]]):
        if len(list(connectors_and_pairs)) <= 1:
            raise ValueError(f"A MultiMarketAssetPriceDelegate requires more than one reference market to be created")

        delegates = []
        previous_trading_pair = None
        for connector, trading_pair in connectors_and_pairs:
            if previous_trading_pair is None:
                previous_trading_pair = trading_pair
                delegates.append(OrderBookAssetPriceDelegate(market=connector, trading_pair=trading_pair))
            else:
                previous_base, previous_quote = split_hb_trading_pair(previous_trading_pair)
                current_base, current_quote = split_hb_trading_pair(trading_pair)

                is_direct_price_converter = current_base == previous_quote
                is_inverse_price_converter = current_quote == previous_quote

                if is_direct_price_converter:
                    previous_trading_pair = trading_pair
                    delegates.append(OrderBookAssetPriceDelegate(market=connector, trading_pair=trading_pair))
                elif is_inverse_price_converter:
                    previous_trading_pair = combine_to_hb_trading_pair(base=current_quote, quote=current_base)
                    delegates.append(OrderBookInverseAssetPriceDelegate.create_for(market=connector,
                                                                                   trading_pair=trading_pair))
                else:
                    raise ValueError(f"It is impossible to configure a price provider combining the prices from "
                                     f"{previous_trading_pair} with the prices from {trading_pair}")

        return cls(price_delegates=delegates)

    @classmethod
    def validate_connectors_and_markets_configuration(cls, connectors_and_pairs: List[Tuple[str, str]]):
        if len(list(connectors_and_pairs)) <= 1:
            raise ValueError(f"A MultiMarketAssetPriceDelegate requires more than one reference market to be created")

        previous_trading_pair = None
        for connector, trading_pair in connectors_and_pairs:
            if previous_trading_pair is None:
                previous_trading_pair = trading_pair
            else:
                previous_base, previous_quote = split_hb_trading_pair(previous_trading_pair)
                current_base, current_quote = split_hb_trading_pair(trading_pair)

                is_direct_price_converter = current_base == previous_quote
                is_inverse_price_converter = current_quote == previous_quote

                if is_direct_price_converter:
                    previous_trading_pair = trading_pair
                elif is_inverse_price_converter:
                    previous_trading_pair = combine_to_hb_trading_pair(base=current_quote, quote=current_base)
                else:
                    raise ValueError(f"It is impossible to configure a price provider combining the prices from "
                                     f"{previous_trading_pair} with the prices from {trading_pair}")

    cdef object c_get_mid_price(self):
        cdef:
            AssetPriceDelegate price_delegate
        resulting_mid_price = Decimal(1)
        for delegate in self._price_delegates:
            price_delegate = delegate
            resulting_mid_price *= price_delegate.c_get_mid_price()
        return resulting_mid_price

    @property
    def ready(self) -> bool:
        return all([market.ready for market in self.all_markets])

    def get_price_by_type(self, price_type: PriceType) -> Decimal:
        resulting_price = Decimal(1)
        for delegate in self._price_delegates:
            price_delegate = delegate
            resulting_price *= price_delegate.get_price_by_type(price_type=price_type)
        return resulting_price

    @property
    def market(self) -> ExchangeBase:
        return None

    @property
    def all_markets(self) -> List[ExchangeBase]:
        return [simple_delegate.market for simple_delegate in self._price_delegates]

    @property
    def all_markets_with_trading_pairs(self) -> List[Tuple[ExchangeBase, str]]:
        result = []
        for price_delegate in self._price_delegates:
            result.extend(price_delegate.all_markets_with_trading_pairs)
        return result

    @property
    def trading_pair(self) -> str:
        first_market_trading_pair = self._price_delegates[0].trading_pair
        last_market_trading_pair = self._price_delegates[-1].trading_pair
        base_asset, _ = split_hb_trading_pair(trading_pair=first_market_trading_pair)
        _, quote_asset = split_hb_trading_pair(trading_pair=last_market_trading_pair)

        trading_pair = combine_to_hb_trading_pair(base=base_asset, quote=quote_asset)
        return trading_pair
