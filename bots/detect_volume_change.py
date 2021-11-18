from helpers.trade_client import get_coin_symbol, get_trading_value
from helpers.update_stored_coins import update_stored_coins
import json
from helpers.send_notification import send_notification
from db.models import CoinScanInfo, ListedCoins
from helpers.logger import getLogger
import time
import threading
from db.main import Database
from gate_api import SpotApi
import redis
from binance.client import Client
from datetime import datetime
import aiohttp
import asyncio
import concurrent.futures

logger = getLogger(__name__)


class DetectVolumeChange:
    def __init__(
        self,
        binance_client: Client,
        gateio_spot_client: SpotApi,
        db_client: Database,
        redis_client: redis.Redis,
        secret_config,
        trade_config,
    ):
        self.binance_client = binance_client
        self.gateio_spot_client = gateio_spot_client
        self.db_client = db_client
        self.redis_client = redis_client
        self.secret_config = secret_config

        self.quantity = trade_config["TRADE_OPTIONS"]["QUANTITY"]
        self.multiplier = trade_config["TRADE_OPTIONS"]["MULTIPLIER"]
        self.avg_size = trade_config["TRADE_OPTIONS"]["AVG_SIZE"]

        self.coin_trade_values = {}
        self.iterations = {}

    async def check_volume(self, coin, session):
        try:
            baseAsset = coin.baseAsset
            quoteAsset = coin.quoteAsset
            default_symbol = baseAsset+quoteAsset
            exchange = 'GATEIO'
            currency_pair = get_coin_symbol(baseAsset, quoteAsset, exchange)

            trade_value = await get_trading_value(
                session=session,
                baseAsset=baseAsset,
                quoteAsset=quoteAsset,
                exchange=exchange,
                redis_client=self.redis_client,
            )

            if currency_pair not in self.coin_trade_values:
                self.coin_trade_values[currency_pair] = [0] * self.avg_size
                self.iterations[currency_pair] = 0

            self.coin_trade_values[currency_pair].pop(0)

            self.coin_trade_values[currency_pair].append(trade_value)

            self.iterations[currency_pair] += 1

            prev_avg_trading_value = sum(
                self.coin_trade_values[currency_pair][:-3]) / (self.avg_size-3)

            curr_avg_trading_value = sum(
                self.coin_trade_values[currency_pair][-3:]) / 3

            if self.iterations[currency_pair] >= self.avg_size:

                if prev_avg_trading_value > 0:

                    largest_deviation_till_now = self.redis_client.get(
                        'largest_deviation_till_now'
                    )
                    if largest_deviation_till_now == None:
                        largest_deviation_till_now = 0
                    else:
                        largest_deviation_till_now = float(
                            largest_deviation_till_now)

                    curr_deviation = curr_avg_trading_value / prev_avg_trading_value

                    if curr_deviation > 1 and curr_deviation > largest_deviation_till_now + 1:
                        self.redis_client.set(
                            'largest_deviation_till_now', curr_deviation
                        )

                        insert_row = CoinScanInfo(
                            baseAsset=baseAsset,
                            quoteAsset=quoteAsset,
                            symbol=default_symbol,
                            price=curr_deviation,
                            exchange=exchange,
                            type="TRACK_LARGEST_DEVIATION",
                        )

                        db_session = self.db_client.session()
                        db_session.add(insert_row)
                        db_session.commit()

                if max(10, prev_avg_trading_value) * self.multiplier < curr_avg_trading_value:
                    logger.info(
                        f"Large deviation detected {currency_pair}")

                    self.redis_client.hset('large_deviation', currency_pair, json.dumps(
                        [{
                            "currency_pair": currency_pair,
                            "coin_trade_values": self.coin_trade_values[currency_pair],
                            "multiplier": self.multiplier,
                        }]
                    ))

                    redis_key = "GATEIO-coin-to-trade"
                    self.redis_client.set(redis_key, json.dumps(
                        [{
                            "baseAsset": baseAsset,
                            "quoteAsset": quoteAsset,
                            "base_amount": self.quantity,
                            "trade_type": "BUY_AND_SELL",
                            "listing_time": datetime.timestamp(datetime.now()),
                        }]
                    ))

                    self.redis_client.set(
                        'largest_deviation_till_now', 0
                    )

                    # with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    #     executor.submit(send_notification, currency_pair, self.secret_config)

        except Exception as e:
            logger.error(f"some error occured {e}")

    async def detect_volume_change(self):
        while True:

            db_session = self.db_client.session()
            coins_to_check = db_session.query(ListedCoins)\
                .filter(ListedCoins.exchange == 'GATEIO').all()

            s = time.perf_counter()
            tasks = []

            async with aiohttp.ClientSession() as session:
                for coin in coins_to_check:
                    tasks.append(self.check_volume(coin, session))

                await asyncio.gather(*tasks, return_exceptions=True)

                elapsed = time.perf_counter() - s
                logger.info(f"elapsed time: {elapsed}")

    def run_bot(self):
        threading.Thread(
            target=update_stored_coins,
            args=(self.binance_client, self.gateio_spot_client, self.db_client,),
        ).start()

        asyncio.run(self.detect_volume_change())
