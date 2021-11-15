from gate_api import SpotApi, Order
from binance.client import Client
import uuid
from datetime import datetime
from helpers.logger import getLogger
import redis

logger = getLogger(__name__)


def get_last_price(symbol, exchange, binance_client: Client, gateio_spot_client: SpotApi):

    last_price = 0

    try:

        if exchange == 'BINANCE':
            coin_info = binance_client.get_symbol_ticker(
                symbol=symbol)
            last_price = coin_info['price']
        elif exchange == 'GATEIO':
            coin_info = gateio_spot_client.list_tickers(
                currency_pair=symbol)

            coin_info = coin_info[0]
            last_price = coin_info.last

        return last_price

    except Exception as _:
        return None


def create_order(
    base_asset,
    quote_asset,
    amount,
    price,
    side,
    exchange,
    trade_config,
    test_mode,
    binance_client: Client,
    gateio_spot_client: SpotApi
):

    default_symbol = base_asset+quote_asset

    response = {
        "amount": str(amount),
        "type": "limit",
        "side": "buy",
        "symbol": default_symbol,
        "price": price,
        "create_time": datetime.timestamp(datetime.now()),
    }

    if test_mode == False:
        if exchange == 'BINANCE':
            created_order = binance_client.create_order(
                {
                    "symbol": default_symbol,
                    "side": side,
                    "type": "market",
                    "quantity": amount,
                }
            )

            response = {
                "amount": str(created_order["price"]),
                "type": created_order["type"],
                "side": created_order["side"],
                "symbol": default_symbol,
                "price": created_order["price"],
                "create_time": created_order["transactTime"]
            }

        elif exchange == 'GATEIO':
            currency_pair = base_asset+'_'+quote_asset
            order = Order(amount=str(amount), type="limit", side=side,
                          currency_pair=currency_pair, price=price)

            created_order = gateio_spot_client.create_order(order)

            response = {
                "amount": str(created_order.amount),
                "type": created_order.type,
                "side": created_order.side,
                "symbol": default_symbol,
                "price": created_order.price,
                "create_time": created_order.create_time
            }

    response["take_profit"] = trade_config['TRADE_OPTIONS']['TP']
    response["stop_loss"] = trade_config['TRADE_OPTIONS']['SL']
    response["upper_circuit"] = trade_config['TRADE_OPTIONS']['UC']
    response["baseAsset"] = base_asset
    response["quoteAsset"] = quote_asset
    response["tradeId"] = str(uuid.uuid4())

    return response


def get_coin_symbol(baseAsset, quoteAsset, exchange):
    if exchange == 'BINANCE':
        return baseAsset+quoteAsset
    elif exchange == 'GATEIO':
        return baseAsset+'_'+quoteAsset
    else:
        return None


async def get_trading_value(
    session,
    baseAsset,
    quoteAsset,
    exchange,
    redis_client: redis.Redis
):
    try:
        symbol = get_coin_symbol(baseAsset, quoteAsset, exchange)

        trading_value = 0
        if exchange == 'GATEIO':
            host = "https://api.gateio.ws"
            prefix = "/api/v4"
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

            url = "/spot/trades"
            query_param = {
                "currency_pair": symbol,
            }

            last_id = redis_client.hget('trade_value_last_id', symbol)
            if last_id != None:
                query_param['last_id'] = last_id
            else:
                query_param['limit'] = 10

            resp = await session.request('GET', url=host + prefix + url, params=query_param, headers=headers)
            trade_info = await resp.json()

            for trade in trade_info:
                if trade['side'] == 'buy':
                    trading_value += (float(trade['amount']) * float(trade['price']))
                    
                    if last_id == None or int(last_id) < int(trade['id']):
                        last_id = trade['id']
            
            if last_id != None:
                redis_client.hset('trade_value_last_id', symbol, last_id)

        elif exchange == 'BINANCE':
            pass # TO DO

        return trading_value
    except Exception as e:
        logger.error(f"Some error occured {e}")
        return 0