from datetime import datetime
from db.main import Database
import json
from new_listings_scraper import get_announced_coin
import time
from gate_api import SpotApi, Order
from logger import getLogger
import redis
from pypika import Table, Query

logger = getLogger(__name__)


class CoinTradingBot:
    def __init__(self, secret_config, trade_config, spot_api: SpotApi, redis_client: redis.Redis, db_client: Database):
        self.secret_config = secret_config
        self.trade_config = trade_config
        self.spot_api_client = spot_api
        self.redis_client = redis_client
        self.db_client = db_client

        self.pairing = trade_config["TRADE_OPTIONS"]["PAIRING"]
        self.quantity = trade_config["TRADE_OPTIONS"]["QUANTITY"]
        self.tp = trade_config["TRADE_OPTIONS"]["TP"]
        self.sl = trade_config["TRADE_OPTIONS"]["SL"]
        self.uc = trade_config["TRADE_OPTIONS"]["UC"]
        self.enable_tsl = trade_config["TRADE_OPTIONS"]["ENABLE_TSL"]
        self.tsl = trade_config["TRADE_OPTIONS"]["TSL"]
        self.ttp = trade_config["TRADE_OPTIONS"]["TTP"]
        self.test_mode = trade_config["TRADE_OPTIONS"]["TEST"]

    def get_coin_to_trade(self):

        coin = self.redis_client.get("gateio-coin-to-trade")
        if coin != None:
            coin = json.loads(coin)

        return coin

    def check_and_sell(self, buy_order):

        while True:

            stored_price = float(buy_order["price"])
            coin_tp = buy_order["tp"]
            coin_sl = buy_order["sl"]
            coin_uc = buy_order["uc"]
            amount = buy_order["amount"]
            currency_pair = buy_order["currency_pair"]

            coin_info = self.spot_api_client.list_tickers(
                currency_pair=currency_pair)
            assert len(coin_info) == 1

            coin_info = coin_info[0]

            last_price = coin_info.last

            coin_symbol_info = currency_pair.split('_')
            insert_obj = {
                "symbol": coin_symbol_info[0],
                "baseCurrency": coin_symbol_info[1],
                "price": last_price,
                "type": "CHECK_AND_SELL",
                "exchange": "GATEIO"
            }
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

            elif float(last_price) < stored_price - (
                stored_price * coin_sl / 100
            ) or float(last_price) > stored_price + (stored_price * coin_uc / 100) or (
                float(last_price)
                > stored_price + (stored_price * coin_tp / 100)
                and not self.enable_tsl
            ):

                try:

                    if not self.test_mode:
                        sell_order = Order(amount=str(amount), type="limit", side='sell',
                                           currency_pair=currency_pair, price=last_price)

                        created_sell_order = self.spot_api_client.create_order(
                            sell_order)
                        sell_order = {
                            "amount": str(created_sell_order.amount),
                            "type": created_sell_order.type,
                            "side": created_sell_order.side,
                            "currency_pair": created_sell_order.currency_pair,
                            "price": created_sell_order.price,
                            "create_time": created_sell_order.create_time
                        }

                    else:
                        sell_order = {
                            "symbol": currency_pair,
                            "price": last_price,
                            "amount": amount,
                            "time": datetime.timestamp(datetime.now()),
                        }

                    sell_order["profit"] = float(last_price) - stored_price
                    sell_order["relative_profit"] = round(
                        (float(last_price) - stored_price)
                        / stored_price
                        * 100,
                        3,
                    )

                    self.redis_client.hset(
                        "soldOrders", currency_pair, json.dumps(sell_order)
                    )

                    logger.info(
                        f"sold {currency_pair} at {(float(last_price) - stored_price) / float(stored_price)*100}"
                    )

                    break

                except Exception as e:
                    logger.exception(e)

            time.sleep(0.1)

    def run_bot(self):
        logger.info("Bot started")

        try:
            coin_to_trade = get_announced_coin(self.redis_client)

            if len(coin_to_trade) > 0:

                symbol = coin_to_trade[0]
                currency_pair = symbol+'_'+self.pairing
                base_amount = self.quantity

                coin_info = self.spot_api_client.list_tickers(
                    currency_pair=currency_pair)

                assert(len(coin_info) == 1)

                coin_info = coin_info[0]
                last_price = coin_info.last

                logger.info(
                    f"Placing buy order for {currency_pair} at {datetime.timestamp(datetime.now())} with base amount {base_amount} and price {last_price}")

                amount = float(base_amount) / float(last_price)

                if self.test_mode == True:
                    buy_order = {
                        "amount": str(amount),
                        "type": "limit",
                        "side": "buy",
                        "currency_pair": currency_pair,
                        "price": last_price
                    }

                else:
                    order = Order(amount=str(amount), type="limit", side='buy',
                                  currency_pair=currency_pair, price=last_price)

                    created_buy_order = self.spot_api_client.create_order(
                        order)
                    buy_order = {
                        "amount": str(created_buy_order.amount),
                        "type": created_buy_order.type,
                        "side": created_buy_order.side,
                        "currency_pair": created_buy_order.currency_pair,
                        "price": created_buy_order.price,
                        "create_time": created_buy_order.create_time
                    }

                buy_order["tp"] = self.tp
                buy_order["sl"] = self.sl
                buy_order["uc"] = self.uc

                self.redis_client.hset(
                    "buyOrders", currency_pair, json.dumps(buy_order)
                )

                insert_obj = {
                    "symbol": symbol,
                    "baseCurrency": self.pairing,
                    "price": buy_order["price"],
                    "type": "BUY",
                    "exchange": "GATEIO"
                }
                insert_query = self.db_client.get_insert_json_query(
                    table_name='CoinScanInfo', json_obj=insert_obj)
                self.db_client.insert_data(insert_query)


                self.check_and_sell(buy_order)

        except Exception as e:
            logger.error(e)
