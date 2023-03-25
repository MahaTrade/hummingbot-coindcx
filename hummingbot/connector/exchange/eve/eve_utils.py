from decimal import Decimal

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

KEYS = {
    "eve_api_key":
        ConfigVar(key="eve_api_key",
                  prompt="Enter your EVE API key >>> ",
                  required_if=using_exchange("eve"),
                  is_secure=True,
                  is_connect_key=True),
    "eve_secret_key":
        ConfigVar(key="eve_secret_key",
                  prompt="Enter your EVE secret key >>> ",
                  required_if=using_exchange("eve"),
                  is_secure=True,
                  is_connect_key=True),
    "eve_user_id":
        ConfigVar(key="eve_user_id",
                  prompt="Enter your EVE user ID >>> ",
                  required_if=using_exchange("eve"),
                  is_secure=True,
                  is_connect_key=True),
}
