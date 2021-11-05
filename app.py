import json
from logging import getLogger
from secret import verify_secret_token
from flask import Flask, request, jsonify
import redis
from load_config import load_config
import requests
import time
from flask_cors import CORS, cross_origin

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

logger = getLogger(__name__)


@app.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There!</h1>"


@app.route('/add-coin', methods=['POST'])
def add_coin():
    try:
        request_data = request.get_json()

        payload = request_data["payload"]
        exchange = request_data["exchange"]
        secret_token = request_data["secret_token"]

        secret_config = load_config("auth/auth.yml")
        redis_client = redis.Redis()

        if verify_secret_token(secret_config, secret_token) == False:
            return jsonify({"data": "Invalid auth token"}), 400

        redis_obj = payload

        redis_key = exchange+"-coin-to-trade"

        redis_client.set(redis_key, json.dumps(redis_obj))

        return jsonify({"status": "PASS"}), 200
    except Exception as e:
        logger.error(f"some error occured: {e}")
        return jsonify({"status": "FAIL", "message": "Some error occured"}), 500


@app.route('/get-chart-data')
@cross_origin()
def get_chart_data():
    try:
        binance_url = "https://api.binance.com/api/v3/klines"
        gateio_url = "https://www.gate.io/json_svr/query"

        curr_timestamp = time.time()
        curr_timestamp *= 1000
        curr_timestamp = int(curr_timestamp)

        start_time = 1620094800000
        end_time = curr_timestamp

        base_currency = request.args.get('base_currency')
        pairing_currency = request.args.get('pairing_currency')

        binance_params = {
            "symbol": base_currency+pairing_currency,
            "interval": "1m",
            "startTime": start_time,
            "endTime": end_time,
            "limit": 100,
        }

        req = requests.get(url=binance_url, params=binance_params)
        binance_response = req.json()

        if binance_response[0] == 0:
            return jsonify(
                {
                    "status": "PASS",
                    "data": {
                        "binance": [],
                        "gateio": []
                    }
                }
            ), 200

        gateio_start_time = binance_response[0][0] - 54000*1000
        gateio_start_time = int(gateio_start_time / 1000)

        gateio_end_time = binance_response[0][6] + 3000*1000
        gateio_end_time = int(gateio_end_time / 1000)

        gateio_params = {
            "u": 10,
            "c": 9025990,
            "type": "tvkline",
            "symbol": base_currency+'_'+pairing_currency,
            "interval": 60,
            "from": gateio_start_time,
            "to": gateio_end_time,
        }

        response = requests.get(url=gateio_url, params=gateio_params)
        response = response.content.decode('ascii')
        response = response.split('\n')[1:]
        gateio_response = [item.split(',') for item in response]

        return jsonify(
            {
                "status": "PASS",
                "data": {
                    "binance": binance_response,
                    "gateio": gateio_response
                }
            }
        ), 200
    except Exception as e:
        logger.error(f"some error occured: {e}")
        return jsonify({"status": "FAIL", "message": "Some error occured"}), 500


if __name__ == "__main__":
    app.run(host='127.0.0.1')
