
from helpers.trade_client import get_coin_symbol, get_last_price
from db.models import CoinScanInfo
from db.main import Database
from binance.client import Client
from helpers.logger import getLogger
import redis
from gate_api import SpotApi
from helpers.logger import getLogger
import json
from helpers.constants import exchanges
import concurrent.futures
import time

logger = getLogger(__name__)


class PriceTracker:

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

        self.pairing = self.trade_config['TRADE_OPTIONS']['PAIRING']

    def get_coins_to_track(self, exchange):
        redis_key = exchange+"-coin-to-track"
        coin = self.redis_client.get(redis_key)
        if coin != None:
            coin = json.loads(coin)

        self.redis_client.delete(redis_key)

        return coin

    def track_price(self, coin, exchange):
        logger.info(f"Starting price tracking for {coin}")
        iterations = 0

        while True:
            coin_symbol = get_coin_symbol(coin, self.pairing, exchange)
            last_price = get_last_price(
                coin_symbol, exchange, self.binance_client, self.gateio_spot_client)

            if last_price != None and last_price != '0':
                insert_row = CoinScanInfo(
                    baseAsset=coin,
                    quoteAsset=self.pairing,
                    symbol=coin_symbol,
                    price=last_price,
                    exchange=exchange,
                    type="TRACK_PRICE",
                )

                db_session = self.db_client.session()
                db_session.add(insert_row)
                db_session.commit()

                iterations += 1
                if iterations >= 100:
                    break
            
            time.sleep(3)

    def run_bot(self):
        logger.info("Bot started...")

        while True:

            for exchange in exchanges:
                coins_to_track = self.get_coins_to_track(exchange)

                if coins_to_track != None:

                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        for coin in coins_to_track:
                            executor.submit(self.track_price, coin, exchange)
            time.sleep(5)
