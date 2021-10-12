import requests
from bs4 import BeautifulSoup
import time
import redis

from logger import getLogger

logger = getLogger(__name__)

def get_last_coin(redis_client: redis.Redis):
    URL = "https://www.binance.com/en/support/announcement/c-48"
    page = requests.get(URL)

    soup = BeautifulSoup(page.content, "html.parser")

    latest_announcement = soup.find(id="link-0-0-p1").text
    
    exclusions = ["Futures", "Margin", "adds"]
    for item in exclusions:
        if item in latest_announcement:
            return []
    
    symbols = []

    if 'Binance Will List'.lower() in latest_announcement.lower():
        str_len = len(latest_announcement)
        for index in range(str_len):
            if latest_announcement[index] == '(':
                symbol = ''
                while index < str_len and latest_announcement[index+1] != ')':
                    index += 1
                    symbol += latest_announcement[index]

                redis_data = redis_client.hget('binance_new_listings', symbol)
                if redis_data == None:
                    symbols.append(symbol)
                    redis_client.hset('binance_new_listings', symbol, "Listed")
    
    return symbols
def get_announced_coin(redis_client: redis.Redis):
    iterations = 0
    while True:
        latest_coin = get_last_coin(redis_client)
        iterations += 1

        if len(latest_coin) > 0:
            return latest_coin

        logger.info(f"Running {iterations}")
        time.sleep(1)
