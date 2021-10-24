
import datetime
import logging
from pytz import timezone, utc


class Formatter(logging.Formatter):
    """override logging.Formatter to use an aware datetime object"""

    def converter(self, timestamp):
        utc_dt = utc.localize(datetime.datetime.utcnow())
        my_tz = timezone("Asia/Kolkata")
        converted = utc_dt.astimezone(my_tz)
        return converted.timetuple()


def getLogger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()

    formatter = Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    ch.setFormatter(formatter)

    logger.addHandler(ch)
    return logger
