import json
from logging import getLogger
from secret import verify_secret_token
from flask import Flask, request, jsonify
import redis
from load_config import load_config

app = Flask(__name__)

logger = getLogger(__name__)


@app.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There!</h1>"


@app.route('/add-coin', methods=['POST'])
def add_coin():
    try:
        request_data = request.get_json()

        currency_pair = request_data["currency_pair"]
        base_amount = request_data["base_amount"]
        listing_time = request_data["listing_time"]
        secret_token = request_data["secret_token"]

        secret_config = load_config("auth/auth.yml")
        redis_client = redis.Redis()

        if verify_secret_token(secret_config, secret_token) == False:
            return jsonify({"data": "Invalid auth token"}), 400

        redis_obj = {
            "currency_pair": currency_pair,
            "base_amount": base_amount,
            "listing_time": listing_time,
        }

        redis_client.set("gateio-coin-to-trade", json.dumps(redis_obj))

        return jsonify({"status": "PASS"}), 200
    except Exception as e:
        logger.error(f"some error occured: {e}")
        return jsonify({"status": "FAIL", "message": "Some error occured"}), 500


if __name__ == "__main__":
    app.run(host='127.0.0.1')
