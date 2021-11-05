from datetime import datetime
from helpers.send_notification import send_notification
from helpers.trade_client import create_order, get_coin_symbol, get_last_price
from db.models import CoinScanInfo
from db.main import Database
import json
import time
from binance.client import Client
from helpers.logger import getLogger
import redis
from gate_api import SpotApi
import threading
import concurrent.futures

logger = getLogger(__name__)


class CoinsTradingBot:
    def __init__(
        self,
        secret_config,
        trade_config,
        binance_client: Client,
        gateio_spot_client: SpotApi,
        redis_client: redis.Redis,
        db_client: Database
    ):
        self.secret_config = secret_config
        self.trade_config = trade_config
        self.binance_client = binance_client
        self.gateio_spot_client = gateio_spot_client
        self.redis_client = redis_client
        self.db_client = db_client

        self.quantity = trade_config["TRADE_OPTIONS"]["QUANTITY"]
        self.take_profit = trade_config["TRADE_OPTIONS"]["TP"]
        self.stop_loss = trade_config["TRADE_OPTIONS"]["SL"]
        self.uc = trade_config["TRADE_OPTIONS"]["UC"]
        self.enable_tsl = trade_config["TRADE_OPTIONS"]["ENABLE_TSL"]
        self.tsl = trade_config["TRADE_OPTIONS"]["TSL"]
        self.ttp = trade_config["TRADE_OPTIONS"]["TTP"]
        self.test_mode = trade_config["TRADE_OPTIONS"]["TEST"]

    def get_coins_to_trade(self, exchange):

        redis_key = exchange+"-coin-to-trade"
        coin = self.redis_client.get(redis_key)
        if coin != None:
            coin = json.loads(coin)

        self.redis_client.delete(redis_key)

        return coin

    def check_and_sell(self, buy_order, exchange):
        baseAsset = buy_order["baseAsset"]
        quoteAsset = buy_order["quoteAsset"]

        while True:
            stored_price = float(buy_order["price"])
            coin_tp = buy_order["take_profit"]
            coin_sl = buy_order["stop_loss"]
            coin_uc = buy_order["upper_circuit"]
            amount = buy_order["amount"]
            symbol = buy_order["symbol"]
            query_symbol = get_coin_symbol(baseAsset, quoteAsset, exchange)

            insert_row = CoinScanInfo(
                baseAsset=baseAsset,
                quoteAsset=quoteAsset,
                symbol=symbol,
                type="CHECK_AND_SELL",
                exchange=exchange,
                tradeId=buy_order["tradeId"]
            )

            last_price = get_last_price(
                query_symbol, exchange, self.binance_client, self.gateio_spot_client)

            insert_row.price = last_price
            db_session = self.db_client.session()
            db_session.add(insert_row)
            db_session.commit()
            db_session.close()

            if (
                float(last_price)
                > stored_price + (stored_price * coin_tp / 100)
                and self.enable_tsl
            ):

                new_tp = float(last_price) + (
                    float(last_price) * self.ttp / 100
                )
                new_tp = float((new_tp - stored_price) / stored_price * 100)

                new_sl = float(last_price) - (
                    float(last_price) * self.tsl / 100
                )
                new_sl = float((stored_price - new_sl) / stored_price * 100)
                new_sl += self.tsl

                buy_order["take_profit"] = new_tp
                buy_order["stop_loss"] = new_sl

                logger.info(
                    f"updated take_profit: {round(new_tp, 3)} and stop_loss: {round(new_sl, 3)}"
                )

                insert_row.type = "UPDAET_TP"
                db_session = self.db_client.session()
                db_session.add(insert_row)
                db_session.commit()
                db_session.close()

            elif float(last_price) < stored_price - (
                stored_price * coin_sl / 100
            ) or float(last_price) > stored_price + (stored_price * coin_uc / 100) or (
                float(last_price)
                > stored_price + (stored_price * coin_tp / 100)
                and not self.enable_tsl
            ):

                try:

                    sell_order = create_order(
                        base_asset=baseAsset,
                        quote_asset=quoteAsset,
                        amount=amount,
                        price=last_price,
                        side='sell',
                        exchange=exchange,
                        trade_config=self.trade_config,
                        test_mode=self.test_mode,
                        binance_client=self.binance_client,
                        gateio_spot_client=self.gateio_spot_client
                    )

                    sell_order["profit"] = float(last_price) - stored_price
                    sell_order["relative_profit"] = round(
                        (float(last_price) - stored_price)
                        / stored_price
                        * 100,
                        3,
                    )

                    self.redis_client.hset(
                        "soldOrders", symbol, json.dumps(
                            sell_order)
                    )

                    logger.info(
                        f"sold {symbol} at {(float(last_price) - stored_price) / float(stored_price)*100}"
                    )

                    insert_row.type = "SELL"
                    db_session = self.db_client.session()
                    db_session.add(insert_row)
                    db_session.commit()
                    db_session.close()

                    break

                except Exception as e:
                    logger.exception(e)

            time.sleep(0.1)

    def buy_and_sell(self, coin_to_trade, exchange):
        if coin_to_trade != None:

            baseAsset = coin_to_trade["baseAsset"]
            quoteAsset = coin_to_trade["quoteAsset"]
            default_symbol = baseAsset+quoteAsset
            query_symbol = get_coin_symbol(baseAsset, quoteAsset, exchange)
            base_amount = coin_to_trade["base_amount"]

            last_price = get_last_price(
                query_symbol, exchange, self.binance_client, self.gateio_spot_client)

            logger.info(
                f"Placing order for {baseAsset} with quote currency {quoteAsset} at {datetime.timestamp(datetime.now())} with base amount {base_amount} and price {last_price}")

            amount = float(base_amount) / float(last_price)

            buy_order = create_order(
                base_asset=baseAsset,
                quote_asset=quoteAsset,
                amount=amount,
                price=last_price,
                side='buy',
                exchange=exchange,
                trade_config=self.trade_config,
                test_mode=self.test_mode,
                binance_client=self.binance_client,
                gateio_spot_client=self.gateio_spot_client
            )

            self.redis_client.hset(
                "buyOrders", default_symbol, json.dumps(buy_order)
            )

            insert_row = CoinScanInfo(
                baseAsset=baseAsset,
                quoteAsset=quoteAsset,
                symbol=default_symbol,
                price=buy_order["price"],
                type="BUY",
                exchange=exchange,
                tradeId=buy_order["tradeId"]
            )

            db_session = self.db_client.session()
            db_session.add(insert_row)
            db_session.commit()

            self.check_and_sell(buy_order, exchange)

    def wait_and_trade(self, coin_to_trade, exchange):
        if coin_to_trade != None:

            baseAsset = coin_to_trade["baseAsset"]
            quoteAsset = coin_to_trade["quoteAsset"]
            symbol = baseAsset+quoteAsset
            listing_time = float(coin_to_trade["listing_time"])
            trade_type = coin_to_trade["trade_type"]

            wait_time = listing_time-datetime.timestamp(datetime.now())

            if wait_time > 0:
                logger.info(
                    f"Found currency pair {symbol}, waiting for {wait_time} seconds before placing order, type: {trade_type}")

                time.sleep(wait_time)

            if trade_type == 'BUY_AND_SELL':
                self.buy_and_sell(coin_to_trade, exchange)
            elif trade_type == 'SELL':
                buy_order = self.redis_client.hget(
                    'buyOrders', symbol)
                buy_order = json.loads(buy_order)

                self.check_and_sell(buy_order, exchange)

    def run_bot(self):
        logger.info("Bot started...")

        while True:

            try:
                exchanges = ['BINANCE', 'GATEIO']
                for exchange in exchanges:
                    coins_to_trade = self.get_coins_to_trade(exchange)

                    if coins_to_trade != None:

                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            for coin in coins_to_trade:
                                coin_info = {
                                    "baseAsset": coin,
                                    "quoteAsset": "USDT",
                                    "base_amount": self.quantity,
                                }

                                executor.submit(self.buy_and_sell, coin_info, exchange)
                            executor.submit(send_notification, coins_to_trade, self.secret_config)

            except Exception as e:
                print(e)
            time.sleep(1)
