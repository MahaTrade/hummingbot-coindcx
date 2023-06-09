import asyncio

from hummingbot.connector.exchange.alpha_point import alpha_point_constants as CONSTANTS
from hummingbot.connector.exchange.alpha_point.alpha_point_auth import AlphaPointAuth
from hummingbot.connector.exchange.alpha_point.alpha_point_web_utils import (
    AlphaPointURLCreatorBase,
    AlphaPointWebAssistantsFactory,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class AlphaPointAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        api_factory: AlphaPointWebAssistantsFactory,
        url_provider: AlphaPointURLCreatorBase,
        oms_id: int,
    ):
        super().__init__()
        self._api_factory = api_factory
        self._auth: AlphaPointAuth = api_factory.auth
        self._url_provider = url_provider
        self._oms_id = oms_id

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        url = self._url_provider.get_ws_url()
        await ws.connect(ws_url=url)
        auth_payload = {
            CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_AUTH_ENDPOINT,
            CONSTANTS.MSG_DATA_FIELD: {},
        }
        auth_request = WSJSONRequest(
            payload=auth_payload, throttler_limit_id=CONSTANTS.WS_AUTH_ENDPOINT, is_auth_required=True
        )
        await ws.send(auth_request)
        return ws

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ensure_authenticated()
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _ensure_authenticated(self):
        if not self._auth.initialized:
            raise RuntimeError("The authenticator is not initialized.")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            payload = {
                CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_ACC_EVENTS_ENDPOINT,
                CONSTANTS.MSG_DATA_FIELD: {
                    CONSTANTS.ACCOUNT_ID_FIELD: self._api_factory.auth.account_id,
                    CONSTANTS.OMS_ID_FIELD: self._oms_id,
                },
            }
            subscribe_account_request = WSJSONRequest(payload=payload, is_auth_required=True)

            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQ_LIMIT_ID):
                await websocket_assistant.send(subscribe_account_request)

            self.logger().info("Subscribed to private account and orders channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data[CONSTANTS.MSG_TYPE_FIELD] == CONSTANTS.EVENT_MSG_TYPE:
                await self._process_event_message(event_message=data, queue=queue)
