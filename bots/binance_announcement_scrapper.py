import json
import redis
from helpers.send_notification import send_notification
from helpers.logger import getLogger
import requests
import time
from requests_ip_rotator import ApiGateway, EXTRA_REGIONS

logger = getLogger(__name__)


class BinanceAnnouncementBot:
    def __init__(self, redis_client: redis.Redis, trade_config):
        self.redis_client = redis_client
        self.domain = "https://www.binance.com"
        self.rotate_ip = trade_config["TRADE_OPTIONS"]["ROTATE_IP"]

        if self.rotate_ip:
            self.gateway = ApiGateway(self.domain)
            self.gateway.start()

            self.session = requests.Session()
            self.session.mount(self.domain, self.gateway)

    def __del__(self):
        if self.rotate_ip:
            self.gateway.shutdown()

    def get_last_coin(self):
        URL = self.domain + "/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=15&rnd=" + \
            str(time.time())

        if self.rotate_ip:
            latest_announcement = self.session.get(URL)
        else:
            latest_announcement = requests.get(URL)
        latest_announcement = latest_announcement.json()
        latest_announcement = latest_announcement['data']['articles'][3]['title']
        symbols = []

        if 'Binance Will List'.lower() in latest_announcement.lower():
            str_len = len(latest_announcement)
            for index in range(str_len):
                if latest_announcement[index] == '(':
                    symbol = ''
                    while index < str_len and latest_announcement[index+1] != ')':
                        index += 1
                        symbol += latest_announcement[index]

                    redis_data = self.redis_client.hget(
                        'binance_new_listings', symbol)
                    if redis_data == None:
                        symbols.append(symbol)
                        self.redis_client.hset(
                            'binance_new_listings', symbol, "Listed")

        return symbols

    def run_bot(self):
        iterations = 0
        while True:
            try:
                latest_coin = self.get_last_coin()
                iterations += 1

                if len(latest_coin) > 0:
                    logger.info(f"New coin(s) detected {latest_coin}")
                    self.redis_client.set('GATEIO-coin-to-trade', json.dumps(latest_coin))

                logger.info(f"Running {iterations}")
                time.sleep(3)
            except Exception as e:
                logger.error(f"Some error occured: {e}")
                time.sleep(5)
