import redis
from helpers.send_notification import send_notification
from helpers.logger import getLogger
import requests
from bs4 import BeautifulSoup
import time
import json

logger = getLogger(__name__)


class GateioVotingAnnouncementBot:
    def __init__(self, redis_client: redis.Redis, secret_config):
        self.secret_config = secret_config
        self.redis_client = redis_client

    def get_last_coin(self):
        URL = "https://www.gate.io"
        page = requests.get(URL+'/poll')

        soup = BeautifulSoup(page.content, "html.parser")

        poll_list = soup.find(id="pollListUl")
        href = poll_list.find_all("a", href=True)
        redis_key = href[0]["href"]

        project_row = soup.find_all("div", {"class": "project-row"})[0]

        children = project_row.find("div")
        curr_announcement = children.contents[0]

        last_announcement = self.redis_client.get(
            'gateio-voting-announcement')

        if last_announcement == None or last_announcement != redis_key:
            self.redis_client.set(
                'gateio-voting-announcement', redis_key)

            str_len = len(curr_announcement)
            symbol = ''

            for index in range(str_len):
                if ord(curr_announcement[index]) == 65288:
                    while index < str_len and ord(curr_announcement[index+1]) != 65289:
                        index += 1
                        symbol += curr_announcement[index]

            if symbol != '':
                logger.info(f"New announcement detected {symbol}")
                
                send_notification(symbol, self.secret_config)
                
                self.redis_client.set(
                    'GATEIO-coin-to-track', json.dumps(symbol)
                )

    def run_bot(self):
        iterations = 0
        while True:
            try:
                self.get_last_coin()
                iterations += 1

                logger.info(f"Running {iterations}")
                time.sleep(10)
            except Exception as e:
                logger.error(f"Some error occured: {e}")
                time.sleep(10)
