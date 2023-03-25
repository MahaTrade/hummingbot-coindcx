import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.huobi import huobi_constants as CONSTANTS, huobi_utils
from hummingbot.connector.exchange.huobi.huobi_exchange import HuobiExchange
from hummingbot.connector.exchange.huobi.huobi_in_flight_order import HuobiInFlightOrder
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class HuobiExchangeTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None

        self.exchange = HuobiExchange(
            huobi_api_key="testAPIKey",
            huobi_secret_key="testSecret",
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

        self._initialize_event_loggers()

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_filled_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="99998888",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "eventType": "trade",
            "symbol": "choinalphahbot",
            "orderId": 99998888,
            "tradePrice": "10050.0",
            "tradeVolume": "0.1",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "10.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        message = {
            "ch": CONSTANTS.HUOBI_TRADE_DETAILS_TOPIC,
            "data": partial_fill
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(partial_fill["feeCurrency"].upper(), Decimal(partial_fill["transactFee"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(partial_fill['tradeVolume'])} out of {order.amount} of order "
            f"{order.order_type.name}-{order.client_order_id}"
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = {
            "eventType": "trade",
            "symbol": "choinalphahbot",
            "orderId": 99998888,
            "tradePrice": "10060.0",
            "tradeVolume": "0.9",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 2,
            "tradeTime": 998787897878,
            "transactFee": "30.0",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        message["data"] = complete_fill

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("40"), order.fee_paid)

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["feeCurrency"].upper(), Decimal(complete_fill["transactFee"]))],
                         fill_event.trade_fee.flat_fees)

        # The order should be marked as complete only when the "done" event arrives, not with the fill event
        self.assertFalse(self._is_logged(
            "INFO",
            f"The LIMIT_BUY order {order.client_order_id} has completed according to order delta websocket API."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_order_fill_event_processed_before_order_complete_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="99998888",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")

        complete_fill = {
            "eventType": "trade",
            "symbol": "choinalphahbot",
            "orderId": 99998888,
            "tradePrice": "10060.0",
            "tradeVolume": "1",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "30.0",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        fill_message = {
            "ch": CONSTANTS.HUOBI_TRADE_DETAILS_TOPIC,
            "data": complete_fill
        }

        update_data = {
            "tradePrice": "10060.0",
            "tradeVolume": "1",
            "tradeId": 1,
            "tradeTime": 1583854188883,
            "aggressor": True,
            "remainAmt": "0.0",
            "execAmt": "1",
            "orderId": 99998888,
            "type": "buy-limit",
            "clientOrderId": "OID1",
            "orderSource": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "orderStatus": "filled",
            "symbol": "btcusdt",
            "eventType": "trade"
        }

        update_message = {
            "action": "push",
            "ch": CONSTANTS.HUOBI_ORDER_UPDATE_TOPIC,
            "data": update_data,
        }

        mock_user_stream = AsyncMock()
        # We simulate the case when the order update arrives before the order fill
        mock_user_stream.get.side_effect = [update_message, fill_message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.async_run_with_timeout(order.wait_until_completely_filled())

        self.assertEqual(Decimal("30"), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["feeCurrency"].upper(), Decimal(complete_fill["transactFee"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(complete_fill['tradeVolume'])} out of {order.amount} of order "
            f"{order.order_type.name}-{order.client_order_id}"
        ))

        self.assertTrue(self._is_logged(
            "INFO",
            f"The {order.trade_type.name} order {order.client_order_id} "
            f"has completed according to order delta websocket API."
        ))

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    @patch("hummingbot.connector.utils.get_tracking_nonce_low_res")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 8

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=self.trading_pair, hbot_order_id_prefix=huobi_utils.BROKER_ID
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=self.trading_pair, hbot_order_id_prefix=huobi_utils.BROKER_ID
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: HuobiInFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + (CONSTANTS.ORDER_MATCHES_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        fill_response = {
            "status": "ok",
            "data": [
                {
                    "symbol": self.base_asset.lower() + self.quote_asset.lower(),
                    "fee-currency": self.quote_asset.lower(),
                    "source": "spot-web",
                    "order-id": order.exchange_order_id,
                    "price": str(order.price + Decimal("50")),
                    "created-at": 1629443051839,
                    "role": "taker",
                    "match-id": 5014,
                    "filled-amount": "0.5",
                    "filled-fees": "30",
                    "filled-points": "0.1",
                    "fee-deduct-currency": "hbpoint",
                    "fee-deduct-state": "done",
                    "trade-id": 1085,
                    "id": 313288753120940,
                    "type": "buy-market"
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(fill_response))

        url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + (CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = {
            "status": "ok",
            "data": {
                "id": 357632718898331,
                "symbol": self.base_asset.lower() + self.quote_asset.lower(),
                "account-id": 13496526,
                "client-order-id": order.client_order_id,
                "amount": str(order.amount),
                "price": str(order.price),
                "created-at": 1630649406687,
                "type": "buy-limit-maker",
                "field-amount": "0.5",
                "field-cash-amount": str(order.price + Decimal("50")),
                "field-fees": "30",
                "finished-at": 0,
                "source": "spot-api",
                "state": "partial-filled",
                "canceled-at": 0
            }
        }

        mock_api.get(regex_url, body=json.dumps(response))

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertEqual("partial-filled", order.last_state)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(float(fill_response["data"][0]["price"]), fill_event.price)
        self.assertEqual(float(fill_response["data"][0]["filled-amount"]), fill_event.amount)
        expected_fill_fee = AddedToCostTradeFee(
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal(fill_response["data"][0]["filled-fees"]))])
        self.assertEqual(expected_fill_fee, fill_event.trade_fee)

    @aioresponses()
    def test_update_order_fill_during_status_update_does_not_process_repeated_trade_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: HuobiInFlightOrder = self.exchange.in_flight_orders["OID1"]

        partial_fill_websocket = {
            "eventType": "trade",
            "symbol": self.base_asset.lower() + self.quote_asset.lower(),
            "orderId": order.exchange_order_id,
            "tradePrice": str(order.price + Decimal("50")),
            "tradeVolume": "0.5",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "30.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": self.quote_asset.lower(),
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": str(order.price),
            "orderSize": str(order.amount),
            "clientOrderId": order.client_order_id,
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        message = {
            "ch": CONSTANTS.HUOBI_TRADE_DETAILS_TOPIC,
            "data": partial_fill_websocket
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal(partial_fill_websocket["transactFee"]), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(partial_fill_websocket["feeCurrency"].upper(),
                                      Decimal(partial_fill_websocket["transactFee"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(partial_fill_websocket['tradeVolume'])} out of {order.amount} of order "
            f"{order.order_type.name}-{order.client_order_id}"
        ))

        url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + (CONSTANTS.ORDER_MATCHES_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        fill_response = {
            "status": "ok",
            "data": [
                {
                    "symbol": self.base_asset.lower() + self.quote_asset.lower(),
                    "fee-currency": self.quote_asset.lower(),
                    "source": "spot-web",
                    "order-id": order.exchange_order_id,
                    "price": str(order.price + Decimal("50")),
                    "created-at": 1629443051839,
                    "role": "taker",
                    "match-id": 5014,
                    "filled-amount": "0.5",
                    "filled-fees": "30",
                    "filled-points": "0.1",
                    "fee-deduct-currency": "hbpoint",
                    "fee-deduct-state": "done",
                    "trade-id": 1,
                    "id": 313288753120940,
                    "type": "buy-market"
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(fill_response))

        url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + (CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = {
            "status": "ok",
            "data": {
                "id": 357632718898331,
                "symbol": self.base_asset.lower() + self.quote_asset.lower(),
                "account-id": 13496526,
                "client-order-id": order.client_order_id,
                "amount": str(order.amount),
                "price": str(order.price),
                "created-at": 1630649406687,
                "type": "buy-limit-maker",
                "field-amount": "0.5",
                "field-cash-amount": str(order.price + Decimal("50")),
                "field-fees": "30",
                "finished-at": 0,
                "source": "spot-api",
                "state": "partial-filled",
                "canceled-at": 0
            }
        }

        mock_api.get(regex_url, body=json.dumps(response))

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
