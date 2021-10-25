from helpers.trade_client import get_trading_value
from helpers.update_stored_coins import update_stored_coins
import json
from helpers.send_notification import send_notification
from db.models import ListedCoins
from helpers.logger import getLogger
import time
import threading
from db.main import Database
from gate_api import SpotApi
import redis
from binance.client import Client
from sqlalchemy import and_
from datetime import datetime
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

        self.coin_trade_values = {}

        self.ten_seconds = 10

        curr_time = time.time()
        self.next_start_window = self.ten_seconds * round(
            curr_time / self.ten_seconds
        )

        self.iterations = 0

        if self.next_start_window < curr_time:
            self.next_start_window += self.ten_seconds

    def check_volume(self, coin):
        baseAsset = coin.baseAsset
        quoteAsset = coin.quoteAsset
        currency_pair = baseAsset+'_'+quoteAsset
        logger.info(f"scanning {currency_pair}")

        trade_value = get_trading_value(
            baseAsset=baseAsset,
            quoteAsset=quoteAsset,
            exchange='GATEIO',
            gateio_spot_client=self.gateio_spot_client,
            binance_client=None
        )

        if currency_pair not in self.coin_trade_values:
            self.coin_trade_values[currency_pair] = [0, 0]

        self.coin_trade_values[currency_pair].pop(0)

        self.coin_trade_values[currency_pair].append(trade_value)

        if trade_value > max(1, self.coin_trade_values[currency_pair][1]) * 1000:
            logger.info(f"Possible new announcement detected {currency_pair}")
            send_notification(currency_pair, self.secret_config)
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

    def detect_volume_change(self):
        while True:

            curr_time = time.time()

            if curr_time >= self.next_start_window:
                if curr_time > self.next_start_window:

                    self.next_start_window = self.ten_seconds * round(
                        curr_time / self.ten_seconds
                    )

                    if self.next_start_window < curr_time:
                        self.next_start_window += self.ten_seconds
                    logger.info(
                        f"Next start window is {self.next_start_window}")

                db_session = self.db_client.session()
                coins_to_check = db_session.query(ListedCoins)\
                    .filter(and_(
                        ListedCoins.exchange == 'GATEIO',
                        ListedCoins.symbol.notin_(
                            db_session.query(ListedCoins.symbol)
                            .filter(ListedCoins.exchange == 'BINANCE')
                        )
                    )).all()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    for coin in coins_to_check:
                        executor.submit(self.check_volume, coin)

            else:
                wait_time = self.next_start_window - curr_time

                logger.info(f"Sleeping for {wait_time} seconds")
                time.sleep(wait_time)

    def run_bot(self):
        threading.Thread(
            target=update_stored_coins,
            args=(self.binance_client, self.gateio_spot_client, self.db_client,),
        ).start()

        threading.Thread(target=self.detect_volume_change, args=()).start()
