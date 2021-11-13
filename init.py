from bots.price_tracker import PriceTracker
from bots.binance_announcement_scrapper import BinanceAnnouncementBot
from bots.gateio_voting_scraper import GateioVotingAnnouncementBot
from bots.coins_trading_bot import CoinsTradingBot
from bots.detect_volume_change import DetectVolumeChange
from db.main import Database
from gate_api import ApiClient, Configuration, SpotApi
from binance.client import Client
import sys
import redis
from load_config import load_config

if __name__ == "__main__":
    try:
        trade_config = load_config("config.yml")
        secret_config = load_config("auth/auth.yml")

        config = Configuration(key=secret_config["gateio_key"],
                               secret=secret_config["gateio_secret"])
        gateio_spot_client = SpotApi(ApiClient(config))

        binance_client = Client(
            api_key=secret_config["binance_api"],
            api_secret=secret_config["binance_secret"],
            tld="com",
        )

        redis_client = redis.Redis()

        db_client = Database(secret_config)

        if len(sys.argv) > 1:

            bot_name = sys.argv[1]
            bot = None

            if bot_name == "coins_trading_bot":
                bot = CoinsTradingBot(
                    secret_config, trade_config, binance_client, gateio_spot_client, redis_client, db_client)

            elif bot_name == "detect_volume_change":
                bot = DetectVolumeChange(
                    binance_client, gateio_spot_client, db_client, redis_client, secret_config, trade_config)

            elif bot_name == "gateio_voting_scraper":
                bot = GateioVotingAnnouncementBot(
                    redis_client, secret_config
                )
            elif bot_name == "binance_announcement_scrapper":
                bot = BinanceAnnouncementBot(redis_client, trade_config)

            elif bot_name == "price_tracker":
                bot = PriceTracker(secret_config, trade_config, binance_client,
                                   gateio_spot_client, redis_client, db_client)

            if bot is not None:
                bot.run_bot()
            else:
                print('Bot parameter was not found')
    except KeyboardInterrupt:
        sys.exit(0)
