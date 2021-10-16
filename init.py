from db.main import Database
from coins_trading_bot import CoinTradingBot
from gate_api import ApiClient, Configuration, SpotApi
import sys
import redis
from load_config import load_config

if __name__ == "__main__":
    try:
        trade_config = load_config("config.yml")
        secret_config = load_config("auth/auth.yml")

        config = Configuration(key=secret_config["gateio_key"],
                            secret=secret_config["gateio_secret"])
        spot_api = SpotApi(ApiClient(config))

        redis_client = redis.Redis()

        db_client = Database(secret_config)
        db_client.connect()

        if len(sys.argv) > 1:

            bot_name = sys.argv[1]
            bot = None

            if bot_name == "coins_trading_bot":
                bot = CoinTradingBot(
                    secret_config, trade_config, spot_api, redis_client, db_client)

            if bot is not None:
                bot.run_bot()
            else:
                print('Bot parameter was not found')
    except KeyboardInterrupt:
        sys.exit(0)
