from sqlalchemy.util.langhelpers import symbol
from db.models import ListedCoins
from db.main import Database
from gate_api import SpotApi
from binance.client import Client
import time

def check_and_insert(listed_coins, exchange, db_client: Database):

    db_session = db_client.session()

    bulk_insert = []

    stored_coins = db_session.query(ListedCoins.symbol)\
        .filter(ListedCoins.exchange == exchange)\
        .all()
    stored_coins_dict = {}

    for coin in stored_coins:
        stored_coins_dict[coin.symbol] = True

    for coin in listed_coins:

        if exchange == 'GATEIO':
            trade_status = coin.trade_status
            if trade_status == 'untradable':
                continue
            coin_symbol = coin.id.replace('_', '')
            baseAsset = coin.base
            quoteAsset = coin.quote
        elif exchange == 'BINANCE':
            trade_status = coin['status']
            if trade_status != 'TRADING':
                continue
            coin_symbol = coin['symbol']
            baseAsset = coin['baseAsset']
            quoteAsset = coin['quoteAsset']

        if coin_symbol not in stored_coins_dict:
            bulk_insert.append(
                ListedCoins(
                    symbol=coin_symbol,
                    baseAsset=baseAsset,
                    quoteAsset=quoteAsset,
                    exchange=exchange
                )
            )

    db_session.bulk_save_objects(bulk_insert)
    db_session.commit()
    db_session.close()


def update_stored_coins(binance_client: Client, gateio_spot_client: SpotApi, db_client: Database):
    while True:
        binance_listed_coins = binance_client.get_exchange_info()['symbols']
        gateio_listed_coins = gateio_spot_client.list_currency_pairs()

        check_and_insert(binance_listed_coins, 'BINANCE', db_client)
        check_and_insert(gateio_listed_coins, 'GATEIO', db_client)

        time.sleep(5 * 60)