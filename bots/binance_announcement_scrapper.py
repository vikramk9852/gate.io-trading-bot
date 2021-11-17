import json
import redis
from helpers.logger import getLogger
import requests
import time
from requests_ip_rotator import ApiGateway
import random
import string

logger = getLogger(__name__)


class BinanceAnnouncementBot:
    def __init__(self, redis_client: redis.Redis, trade_config):
        self.redis_client = redis_client
        self.domain = "https://www.binancezh.com"
        self.rotate_ip = trade_config["TRADE_OPTIONS"]["ROTATE_IP"]

        if self.rotate_ip:
            logger.info("setting up gateway")
            self.gateway = ApiGateway(self.domain)
            self.gateway.start()

            logger.info("setting up session")
            self.session = requests.Session()
            self.session.mount(self.domain, self.gateway)

    def __del__(self):
        if self.rotate_ip:
            logger.info("Closing gateway")
            self.gateway.shutdown()

    def get_last_coin(self):
            
        rand_page_size = random.randint(1, 200)
        letters = string.ascii_letters
        random_string = ''.join(random.choice(letters) for i in range(random.randint(10, 20)))
        random_number = random.randint(1, 99999999999999999999)
        queries = ["type=1", "catalogId=48", "pageNo=1", f"pageSize={str(rand_page_size)}", f"rnd={str(time.time())}",
                f"{random_string}={str(random_number)}"]
        random.shuffle(queries)
        URL = f"{self.domain}/gateway-api/v1/public/cms/article/list/query" \
                  f"?{queries[0]}&{queries[1]}&{queries[2]}&{queries[3]}&{queries[4]}&{queries[5]}"

        if self.rotate_ip:
            latest_announcement = self.session.get(URL)
        else:
            latest_announcement = requests.get(URL)
        
        latest_announcement = latest_announcement.json()
        latest_announcement = latest_announcement['data']['catalogs'][0]['articles'][0]['title']
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
        else:
            binance_last_announcement = self.redis_client.get(
                'binance_last_announcement')
            if binance_last_announcement == None or binance_last_announcement != latest_announcement:
                logger.info(
                    f"latest announcement from binance {latest_announcement}")
                self.redis_client.set('binance_last_announcement', latest_announcement)

        return symbols

    def run_bot(self):
        iterations = 0
        while True:
            try:
                latest_coin = self.get_last_coin()
                iterations += 1

                if len(latest_coin) > 0:
                    logger.info(f"New coin(s) detected {latest_coin}")
                    self.redis_client.set(
                        'GATEIO-coin-to-trade', json.dumps(latest_coin))

                logger.info(f"Running {iterations}")
                time.sleep(3)
            except Exception as e:
                logger.error(f"Some error occured: {e}")
                self.redis_client.delete('binance_last_announcement')
                time.sleep(5)
