import asyncio
import unittest
from copy import deepcopy
from typing import Awaitable
from unittest.mock import patch

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import (
    maker_trading_pair_prompt,
    on_validate_price_source,
    order_amount_prompt,
    pure_market_making_config_map as pmm_config_map,
    validate_decimal_list,
    validate_price_source_exchange,
    validate_price_type,
)


class TestPMMConfigMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.exchange = "binance"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(pmm_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            pmm_config_map[key] = value

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_on_validate_price_source_non_external_market_reset(self):
        pmm_config_map["price_source_exchange"].value = "an_extmkt"
        pmm_config_map["price_source_market"].value = self.trading_pair
        pmm_config_map["take_if_crossed"].value = False

        on_validate_price_source(value="current_market")

        self.assertIsNone(pmm_config_map["price_source_exchange"].value)
        self.assertIsNone(pmm_config_map["price_source_market"].value)
        self.assertIsNone(pmm_config_map["take_if_crossed"].value)

    def test_on_validate_price_source_non_custom_api_reset(self):
        pmm_config_map["price_source_custom_api"].value = "https://someurl.com"

        on_validate_price_source(value="current_market")

        self.assertIsNone(pmm_config_map["price_source_custom_api"].value)

    def test_on_validate_price_source_custom_api_set_price_type(self):
        on_validate_price_source(value="custom_api")

        self.assertEqual(pmm_config_map["price_type"].value, "custom")

    def test_validate_price_type_non_custom_api(self):
        pmm_config_map["price_source"].value = "current_market"

        error = validate_price_type(value="mid_price")
        self.assertIsNone(error)
        error = validate_price_type(value="last_price")
        self.assertIsNone(error)
        error = validate_price_type(value="last_own_trade_price")
        self.assertIsNone(error)
        error = validate_price_type(value="best_bid")
        self.assertIsNone(error)
        error = validate_price_type(value="best_ask")
        self.assertIsNone(error)
        error = validate_price_type(value="inventory_cost")
        self.assertIsNone(error)

        error = validate_price_type(value="custom")
        self.assertIsNotNone(error)

    def test_validate_price_type_custom_api(self):
        pmm_config_map["price_source"].value = "custom_api"

        error = validate_price_type(value="mid_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="last_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="last_own_trade_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="best_bid")
        self.assertIsNotNone(error)
        error = validate_price_type(value="best_ask")
        self.assertIsNotNone(error)
        error = validate_price_type(value="inventory_cost")
        self.assertIsNotNone(error)

        error = validate_price_type(value="custom")
        self.assertIsNone(error)

    def test_order_amount_prompt(self):
        pmm_config_map["market"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)

    def test_maker_trading_pair_prompt(self):
        pmm_config_map["exchange"].value = self.exchange
        example = AllConnectorSettings.get_example_pairs().get(self.exchange)

        prompt = maker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_validate_price_source_exchange(self):
        pmm_config_map["exchange"].value = self.exchange
        self.assertEqual(validate_price_source_exchange(value='binance'),
                         'Price source exchange cannot be the same as maker exchange.')
        self.assertIsNone(validate_price_source_exchange(value='kucoin'))
        self.assertIsNone(validate_price_source_exchange(value='binance_perpetual'))

    def test_validate_decimal_list(self):
        error = validate_decimal_list(value="1")
        self.assertIsNone(error)
        error = validate_decimal_list(value="1,2")
        self.assertIsNone(error)
        error = validate_decimal_list(value="asd")
        expected = "Please enter valid decimal numbers"
        self.assertEqual(expected, error)

    def test_validate_multi_market_price_sources_fails_with_one_market(self):
        pmm_config_map["price_source_exchanges_and_markets"].value = "binance:TOK1-TOK2"

        expected_error = "The multi_market price source requires at least two reference markets."
        error = self.async_run_with_timeout(pmm_config_map["price_source_exchanges_and_markets"].validate(
            pmm_config_map["price_source_exchanges_and_markets"].value))

        self.assertEqual(expected_error, error)

    def test_validate_multi_market_price_sources_fails_when_a_market_pair_is_malformed(self):
        pmm_config_map["price_source_exchanges_and_markets"].value = "binance:TOK1-TOK2,binanceTOK2-TOK3"

        expected_error = "The value binanceTOK2-TOK3 is not a valid exchange:market pair"
        error = self.async_run_with_timeout(pmm_config_map["price_source_exchanges_and_markets"].validate(
            pmm_config_map["price_source_exchanges_and_markets"].value))

        self.assertEqual(expected_error, error)

    def test_validate_multi_market_price_sources_fails_if_markets_cant_be_connected(self):
        pmm_config_map["price_source_exchanges_and_markets"].value = "binance:TOK1-TOK2,binance:TOK30-TOK40"

        expected_error = "It is impossible to configure a price provider combining the prices from TOK1-TOK2 with the " \
                         "prices from TOK30-TOK40"
        error = self.async_run_with_timeout(pmm_config_map["price_source_exchanges_and_markets"].validate(
            pmm_config_map["price_source_exchanges_and_markets"].value))

        self.assertEqual(expected_error, error)

    @patch("hummingbot.strategy.pure_market_making.pure_market_making_config_map.validate_market_trading_pair")
    def test_validate_multi_market_price_sources_fails_with_invalid_markets(self, validation_mock):
        validation_mock.return_value = "Invalid trading pair"
        pmm_config_map["price_source_exchanges_and_markets"].value = "binance:TOK1-TOK2,binance:TOK2-TOK3"

        expected_error = "Invalid trading pair\nInvalid trading pair"
        error = self.async_run_with_timeout(pmm_config_map["price_source_exchanges_and_markets"].validate(
            pmm_config_map["price_source_exchanges_and_markets"].value))

        self.assertEqual(expected_error, error)

    @patch("hummingbot.strategy.pure_market_making.pure_market_making_config_map.validate_market_trading_pair")
    def test_validate_multi_market_price_sources_successfully(self, validation_mock):
        validation_mock.return_value = None
        pmm_config_map["price_source_exchanges_and_markets"].value = "binance:TOK1-TOK2,binance:TOK2-TOK3"

        error = self.async_run_with_timeout(pmm_config_map["price_source_exchanges_and_markets"].validate(
            pmm_config_map["price_source_exchanges_and_markets"].value))

        self.assertIsNone(error)

    def test_validate_price_source(self):
        for price_source in ["current_market", "external_market", "multi_market", "custom_api"]:
            pmm_config_map["price_source"].value = price_source
            validation_result = self.async_run_with_timeout(pmm_config_map["price_source"].validate(
                pmm_config_map["price_source"].value))
            self.assertIsNone(validation_result)

        pmm_config_map["price_source"].value = "invalid_source"
        validation_result = self.async_run_with_timeout(pmm_config_map["price_source"].validate(
            pmm_config_map["price_source"].value))
        self.assertEqual("Invalid price source type.", validation_result)
