import redis
from helpers.send_notification import send_notification
from helpers.logger import getLogger
import requests
from bs4 import BeautifulSoup
import time

logger = getLogger(__name__)


class NewAnnouncementBot:
    def __init__(self, redis_client: redis.Redis, secret_config):
        self.secret_config = secret_config
        self.redis_client = redis_client

    def get_last_coin(self):
        URL = "https://www.gate.io/poll"
        page = requests.get(URL)

        soup = BeautifulSoup(page.content, "html.parser")
        soup = soup.find(id="pollListUl")

        children = soup.find_all("a", href=True)
        last_announcement = self.redis_client.get(
            'gateio-voting-announcement')
        curr_announcement = children[0]['href']

        if last_announcement == None or last_announcement.decode('ascii') != curr_announcement:
            send_notification(last_announcement, self.secret_config)
            self.redis_client.set(
            'gateio-voting-announcement', curr_announcement)

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
