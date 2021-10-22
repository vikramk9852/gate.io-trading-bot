from datetime import datetime
from db.main import Database
import json
import time
from binance.client import Client
from logger import getLogger
import redis
import uuid
import threading

logger = getLogger(__name__)


class BinanceTradingBot:
    def __init__(self, secret_config, trade_config, binance_client: Client, redis_client: redis.Redis, db_client: Database):
        self.secret_config = secret_config
        self.trade_config = trade_config
        self.binance_client = binance_client
        self.redis_client = redis_client
        self.db_client = db_client

        self.tp = trade_config["TRADE_OPTIONS"]["TP"]
        self.sl = trade_config["TRADE_OPTIONS"]["SL"]
        self.uc = trade_config["TRADE_OPTIONS"]["UC"]
        self.enable_tsl = trade_config["TRADE_OPTIONS"]["ENABLE_TSL"]
        self.tsl = trade_config["TRADE_OPTIONS"]["TSL"]
        self.ttp = trade_config["TRADE_OPTIONS"]["TTP"]
        self.test_mode = trade_config["TRADE_OPTIONS"]["TEST"]

    def get_coins_to_trade(self):

        redis_key = "BINANCE-coin-to-trade"
        coin = self.redis_client.get(redis_key)
        if coin != None:
            coin = json.loads(coin)

        self.redis_client.delete(redis_key)

        return coin

    def check_and_sell(self, buy_order):
        symbol = buy_order["symbol"]
        pairing = buy_order["pairing"]
        tradeId = buy_order["tradeId"]

        insert_obj = {
            "symbol": symbol,
            "baseCurrency": pairing,
            "type": "CHECK_AND_SELL",
            "exchange": "BINANCE",
            "tradeId": tradeId
        }

        while True:

            stored_price = float(buy_order["price"])
            coin_tp = buy_order["tp"]
            coin_sl = buy_order["sl"]
            coin_uc = buy_order["uc"]
            amount = buy_order["amount"]
            default_currency_pair = buy_order["currency_pair"]
            binance_currency_pair = symbol+pairing

            coin_info = self.binance_client.get_symbol_ticker(
                symbol=binance_currency_pair)

            last_price = coin_info["price"]

            insert_obj["price"] = last_price

            insert_query = self.db_client.get_insert_json_query(
                table_name='CoinScanInfo', json_obj=insert_obj)
            self.db_client.insert_data(insert_query)

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

                buy_order["tp"] = new_tp
                buy_order["sl"] = new_sl

                logger.info(
                    f"updated tp: {round(new_tp, 3)} and sl: {round(new_sl, 3)}"
                )

                insert_obj["type"] = "UPDAET_TP"
                insert_query = self.db_client.get_insert_json_query(
                    table_name='CoinScanInfo', json_obj=insert_obj)
                self.db_client.insert_data(insert_query)

            elif float(last_price) < stored_price - (
                stored_price * coin_sl / 100
            ) or float(last_price) > stored_price + (stored_price * coin_uc / 100) or (
                float(last_price)
                > stored_price + (stored_price * coin_tp / 100)
                and not self.enable_tsl
            ):

                try:

                    if self.test_mode == True:
                        sell_order = {
                            "currency_pair": default_currency_pair,
                            "price": last_price,
                            "amount": amount,
                            "create_time": datetime.timestamp(datetime.now()),
                            "type": "market",
                            "side": "sell"
                        }
                    else:
                        created_sell_order = self.binance_client.create_order(
                            {
                                "symbol": binance_currency_pair,
                                "side": "sell",
                                "type": "market",
                                "quantity": amount,

                            }
                        )
                        sell_order = {
                            "amount": str(created_sell_order["executedQty"]),
                            "type": created_sell_order["type"],
                            "side": created_sell_order["side"],
                            "currency_pair": created_sell_order["symbol"],
                            "price": created_sell_order["price"],
                            "create_time": created_sell_order["transactTime"]
                        }

                    sell_order["profit"] = float(last_price) - stored_price
                    sell_order["relative_profit"] = round(
                        (float(last_price) - stored_price)
                        / stored_price
                        * 100,
                        3,
                    )

                    self.redis_client.hset(
                        "soldOrders", default_currency_pair, json.dumps(
                            sell_order)
                    )

                    logger.info(
                        f"sold {default_currency_pair} at {(float(last_price) - stored_price) / float(stored_price)*100}"
                    )

                    insert_obj["type"] = "SELL"
                    insert_query = self.db_client.get_insert_json_query(
                        table_name='CoinScanInfo', json_obj=insert_obj)
                    self.db_client.insert_data(insert_query)

                    break

                except Exception as e:
                    logger.exception(e)

            time.sleep(0.1)

    def buy_and_sell(self, coin_to_trade):
        if coin_to_trade != None:

            symbol = coin_to_trade["symbol"]
            pairing = coin_to_trade["pairing"]
            default_currency_pair = symbol+'_'+pairing
            binance_currency_pair = symbol+pairing
            base_amount = coin_to_trade["base_amount"]

            coin_info = self.binance_client.get_symbol_ticker(
                symbol=binance_currency_pair)

            last_price = coin_info["price"]

            logger.info(
                f"Placing order for {default_currency_pair} at {datetime.timestamp(datetime.now())} with base amount {base_amount} and price {last_price}")

            amount = float(base_amount) / float(last_price)

            if self.test_mode == True:
                buy_order = {
                    "amount": str(amount),
                    "type": "limit",
                    "side": "buy",
                    "currency_pair": default_currency_pair,
                    "price": last_price,
                    "create_time": datetime.timestamp(datetime.now()),
                }

            else:
                created_buy_order = self.binance_client.create_order(
                    {
                        "symbol": binance_currency_pair,
                        "side": "buy",
                        "type": "market",
                        "quantity": amount,

                    }
                )
                buy_order = {
                    "amount": str(created_buy_order["executedQty"]),
                    "type": created_buy_order["type"],
                    "side": created_buy_order["side"],
                    "currency_pair": created_buy_order["symbol"],
                    "price": created_buy_order["price"],
                    "create_time": created_buy_order["transactTime"]
                }

            buy_order["tp"] = self.tp
            buy_order["sl"] = self.sl
            buy_order["uc"] = self.uc
            buy_order["symbol"] = symbol
            buy_order["pairing"] = pairing
            buy_order["tradeId"] = str(uuid.uuid4())

            self.redis_client.hset(
                "buyOrders", default_currency_pair, json.dumps(buy_order)
            )

            insert_obj = {
                "symbol": symbol,
                "baseCurrency": pairing,
                "price": buy_order["price"],
                "type": "BUY",
                "exchange": "BINANCE",
                "tradeId": buy_order["tradeId"]
            }
            insert_query = self.db_client.get_insert_json_query(
                table_name='CoinScanInfo', json_obj=insert_obj)
            self.db_client.insert_data(insert_query)

            self.check_and_sell(buy_order)

    def wait_and_trade(self, coin_to_trade):
        if coin_to_trade != None:

            symbol = coin_to_trade["symbol"]
            pairing = coin_to_trade["pairing"]
            default_currency_pair = symbol+'_'+pairing
            listing_time = float(coin_to_trade["listing_time"])
            trade_type = coin_to_trade["trade_type"]

            wait_time = listing_time-datetime.timestamp(datetime.now())

            logger.info(
                f"Found currency pair {default_currency_pair}, waiting for {wait_time} seconds before placing order, type: {trade_type}")

            time.sleep(wait_time)

            if trade_type == 'BUY_AND_SELL':
                self.buy_and_sell(coin_to_trade)
            elif trade_type == 'SELL':
                buy_order = self.redis_client.hget(
                    'buyOrders', default_currency_pair)
                buy_order = json.loads(buy_order)

                self.check_and_sell(buy_order)

    def run_bot(self):
        logger.info("Bot started...")

        while True:

            try:
                coins_to_trade = self.get_coins_to_trade()

                if coins_to_trade != None:
                    for coin in coins_to_trade:
                        threading.Thread(
                            target=self.wait_and_trade,
                            args=(coin,),
                        ).start()

            except Exception as e:
                print(e)
            time.sleep(5)
