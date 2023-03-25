from decimal import Decimal
from typing import Dict
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.data_type.order_book import OrderBook, OrderBookRow
from hummingbot.strategy.multi_market_asset_price_delegate import MultiMarketAssetPriceDelegate


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


class MultiMarketAssetPriceDelegateTests(TestCase):

    def test_instance_creation_with_no_reference_markets_fails(self):
        with self.assertRaises(ValueError) as context:
            MultiMarketAssetPriceDelegate.for_markets([])

        self.assertEqual("A MultiMarketAssetPriceDelegate requires more than one reference market to be created",
                         str(context.exception))

    def test_instance_creation_with_one_reference_markets_fails(self):
        market = MagicMock()
        trading_pair = "COINALPHA-HBOT"
        market_and_token = (market, trading_pair)
        with self.assertRaises(ValueError) as context:
            MultiMarketAssetPriceDelegate.for_markets([market_and_token])

        self.assertEqual("A MultiMarketAssetPriceDelegate requires more than one reference market to be created",
                         str(context.exception))

    def test_instance_creation_finishes_successfully(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = MagicMock()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book
        second_trading_pair = "TOK2-TOK3"
        second_trading_pair_order_book = MagicMock()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book

        delegate = MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                              (second_connector, second_trading_pair)])

        self.assertEqual("TOK1-TOK3", delegate.trading_pair)
        self.assertEqual([first_connector, second_connector], delegate.all_markets)
        self.assertIsNone(delegate.market)

    def test_multi_market_delegate_is_ready_when_all_its_delegates_are_ready(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = OrderBook()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book

        second_trading_pair = "TOK2-TOK3"
        second_trading_pair_order_book = OrderBook()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book

        delegate = MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                              (second_connector, second_trading_pair)])

        self.assertFalse(delegate.ready)

        first_connector._ready = True
        self.assertFalse(delegate.ready)

        second_connector._ready = True
        self.assertTrue(delegate.ready)

    def test_instance_creation_fails_if_connected_trading_pairs_have_no_common_token(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = MagicMock()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book
        second_trading_pair = "TOK2-TOK3"
        second_trading_pair_order_book = MagicMock()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book
        third_trading_pair = "TOK8-TOK9"
        third_trading_pair_order_book = MagicMock()
        third_connector = MockExchange()
        third_connector._order_books[third_trading_pair] = third_trading_pair_order_book

        with self.assertRaises(ValueError) as context:
            MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                       (second_connector, second_trading_pair),
                                                       (third_connector, third_trading_pair)])

        self.assertEqual(f"It is impossible to configure a price provider combining the prices from "
                         f"{second_trading_pair} with the prices from {third_trading_pair}",
                         str(context.exception))

    def test_instance_creation_uses_inverse_delegate_when_second_market_quote_equals_first_market_quote(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = MagicMock()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book
        second_trading_pair = "TOK3-TOK2"
        second_trading_pair_order_book = MagicMock()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book

        delegate = MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                              (second_connector, second_trading_pair)])

        self.assertEqual("TOK1-TOK3", delegate.trading_pair)
        all_markets = delegate.all_markets
        self.assertEqual([first_connector, second_connector], all_markets)
        self.assertIn("TOK1-TOK2", all_markets[0]._order_books)
        self.assertIn("TOK3-TOK2", all_markets[1]._order_books)
        self.assertNotIn("TOK2-TOK3", all_markets[1]._order_books)

    def test_get_price_when_configured_with_direct_delegates(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = OrderBook()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=first_trading_pair_order_book,
            bid_price=90.0,
            ask_price=110.0)

        second_trading_pair = "TOK2-TOK3"
        second_trading_pair_order_book = OrderBook()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=second_trading_pair_order_book,
            bid_price=120.0,
            ask_price=125.0)

        third_trading_pair = "TOK3-TOK4"
        third_trading_pair_order_book = OrderBook()
        third_connector = MockExchange()
        third_connector._order_books[third_trading_pair] = third_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=third_trading_pair_order_book,
            bid_price=0.4,
            ask_price=0.6)

        delegate = MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                              (second_connector, second_trading_pair),
                                                              (third_connector, third_trading_pair)])

        expected_mid_price = ((110 + 90) / 2) * ((125 + 120) / 2) * ((0.6 + 0.4) / 2)
        self.assertEqual(expected_mid_price, delegate.get_mid_price())
        self.assertEqual(expected_mid_price, delegate.get_price_by_type(price_type=PriceType.MidPrice))

    def test_get_price_when_configured_with_one_direct_and_two_indirect_delegates(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = OrderBook()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=first_trading_pair_order_book,
            bid_price=90.0,
            ask_price=110.0)

        second_trading_pair = "TOK3-TOK2"
        second_trading_pair_order_book = OrderBook()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=second_trading_pair_order_book,
            bid_price=120.0,
            ask_price=125.0)

        third_trading_pair = "TOK4-TOK3"
        third_trading_pair_order_book = OrderBook()
        third_connector = MockExchange()
        third_connector._order_books[third_trading_pair] = third_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=third_trading_pair_order_book,
            bid_price=0.4,
            ask_price=0.6)

        delegate = MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                              (second_connector, second_trading_pair),
                                                              (third_connector, third_trading_pair)])

        expected_first_market_mid_price = Decimal(str((110 + 90) / 2))
        expected_second_market_mid_price = Decimal("1") / Decimal(str(((125 + 120) / 2)))
        expected_third_market_mid_price = Decimal("1") / Decimal(str((0.6 + 0.4) / 2))
        expected_mid_price = (expected_first_market_mid_price
                              * expected_second_market_mid_price
                              * expected_third_market_mid_price)
        self.assertEqual(expected_mid_price, delegate.get_mid_price())
        self.assertEqual(expected_mid_price, delegate.get_price_by_type(price_type=PriceType.MidPrice))
        self.assertEqual("TOK1-TOK4", delegate.trading_pair)

    def test_get_price_when_configured_with_two_direct_and_two_indirect_delegates(self):
        first_trading_pair = "TOK1-TOK2"
        first_trading_pair_order_book = OrderBook()
        first_connector = MockExchange()
        first_connector._order_books[first_trading_pair] = first_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=first_trading_pair_order_book,
            bid_price=90.0,
            ask_price=110.0)

        second_trading_pair = "TOK3-TOK2"
        second_trading_pair_order_book = OrderBook()
        second_connector = MockExchange()
        second_connector._order_books[second_trading_pair] = second_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=second_trading_pair_order_book,
            bid_price=120.0,
            ask_price=125.0)

        third_trading_pair = "TOK4-TOK3"
        third_trading_pair_order_book = OrderBook()
        third_connector = MockExchange()
        third_connector._order_books[third_trading_pair] = third_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=third_trading_pair_order_book,
            bid_price=0.4,
            ask_price=0.6)

        fourth_trading_pair = "TOK4-TOK5"
        fourth_trading_pair_order_book = OrderBook()
        fourth_connector = MockExchange()
        fourth_connector._order_books[fourth_trading_pair] = fourth_trading_pair_order_book
        self._configure_order_book_prices(
            order_book=fourth_trading_pair_order_book,
            bid_price=200.5,
            ask_price=202.7)

        delegate = MultiMarketAssetPriceDelegate.for_markets([(first_connector, first_trading_pair),
                                                              (second_connector, second_trading_pair),
                                                              (third_connector, third_trading_pair),
                                                              (fourth_connector, fourth_trading_pair)])

        expected_first_market_mid_price = Decimal(str((110 + 90) / 2))
        expected_second_market_mid_price = Decimal("1") / Decimal(str(((125 + 120) / 2)))
        expected_third_market_mid_price = Decimal("1") / Decimal(str((0.6 + 0.4) / 2))
        expected_fourth_market_mid_price = Decimal(str((200.5 + 202.7) / 2))
        expected_mid_price = (expected_first_market_mid_price
                              * expected_second_market_mid_price
                              * expected_third_market_mid_price
                              * expected_fourth_market_mid_price)
        self.assertEqual(expected_mid_price, delegate.get_mid_price())
        self.assertEqual(expected_mid_price, delegate.get_price_by_type(price_type=PriceType.MidPrice))
        self.assertEqual("TOK1-TOK5", delegate.trading_pair)

    def _configure_order_book_prices(self, order_book: OrderBook, bid_price: float, ask_price: float):
        order_book.apply_snapshot(
            bids=[OrderBookRow(bid_price, 10, 1)],
            asks=[OrderBookRow(ask_price, 15, 1)],
            update_id=1)
