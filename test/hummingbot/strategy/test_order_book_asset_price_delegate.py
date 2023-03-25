from typing import Dict
from unittest import TestCase

from hummingbot.connector.exchange_base import Decimal, ExchangeBase
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.data_type.order_book import OrderBook, OrderBookRow
from hummingbot.strategy.order_book_asset_price_delegate import (
    OrderBookAssetPriceDelegate,
    OrderBookInverseAssetPriceDelegate,
)


class MockExchange(ExchangeBase):

    def __init__(self):
        super().__init__()
        self._order_books: Dict[str, OrderBook] = {}
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_books[trading_pair]

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("0.001")


class OrderBookInverseAssetPriceDelegateTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._market = MockExchange()
        self._order_book = OrderBook()
        self._trading_pair = "COINALPHA-HBOT"
        self._market._order_books[self._trading_pair] = self._order_book
        self._direct_delegate = OrderBookAssetPriceDelegate(market=self._market, trading_pair=self._trading_pair)
        self._inverse_delegate = OrderBookInverseAssetPriceDelegate(direct_delegate=self._direct_delegate)

        self._order_book.apply_snapshot(
            bids=[OrderBookRow(9998.5, 10, 1)],
            asks=[OrderBookRow(10004.4, 15, 1)],
            update_id=1)

    def test_instance_creation_with_connector_and_trading_pair(self):
        inverse_delegate = OrderBookInverseAssetPriceDelegate.create_for(market=self._market,
                                                                         trading_pair=self._trading_pair)
        self.assertEqual(self._inverse_delegate.get_mid_price(), inverse_delegate.get_mid_price())
        self.assertEqual(self._inverse_delegate.market, inverse_delegate.market)
        self.assertEqual(self._inverse_delegate.get_price_by_type(price_type=PriceType.BestBid),
                         inverse_delegate.get_price_by_type(price_type=PriceType.BestBid))

    def test_get_price_returns_inverted_price(self):
        direct_mid_price = self._direct_delegate.get_mid_price()
        inverse_mid_price = self._inverse_delegate.get_mid_price()

        self.assertEqual(inverse_mid_price, Decimal(1) / direct_mid_price)

    def test_get_price_by_type_returns_inverted_price(self):
        direct_price = self._direct_delegate.get_price_by_type(price_type=PriceType.MidPrice)
        inverse_price = self._inverse_delegate.get_price_by_type(price_type=PriceType.MidPrice)

        self.assertEqual(inverse_price, Decimal(1) / direct_price)

    def test_ready_state(self):
        self.assertFalse(self._inverse_delegate.ready)

        self._market._ready = True
        self.assertTrue(self._inverse_delegate.ready)

    def test_access_market_and_markets(self):
        self.assertEqual(self._market, self._inverse_delegate.market)
        self.assertEqual([self._market], self._inverse_delegate.all_markets)

    def test_inverse_delegate_inverts_trading_pair(self):
        base, quote = split_hb_trading_pair(self._trading_pair)
        inverted_trading_pair = combine_to_hb_trading_pair(base=quote, quote=base)

        self.assertEqual(inverted_trading_pair, self._inverse_delegate.trading_pair)
