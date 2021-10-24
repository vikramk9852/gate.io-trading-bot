from gate_api import SpotApi, Order
from binance.client import Client
import uuid
from datetime import datetime


def get_last_price(symbol, exchange, binance_client: Client, gateio_spot_client: SpotApi):

    last_price = 0

    if exchange == 'BINANCE':
        last_price = binance_client.get_symbol_ticker(
            symbol=symbol)
    elif exchange == 'GATEIO':
        coin_info = gateio_spot_client.list_tickers(
            currency_pair=symbol)

        coin_info = coin_info[0]
        last_price = coin_info.last

    return last_price


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
