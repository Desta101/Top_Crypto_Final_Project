from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from data.coins import coins
from predictions import update_coins_predictions, predict_next_7_days, get_coins_predictions
from utils.utils import api_get_response
from invetment import find_best_subset, split_invest_in_subset

app = Flask(__name__)
CORS(app)
scheduler = BackgroundScheduler()


@app.route('/invest', methods=['POST'])
def invest():
    investment = request.json.get('investment', 0)
    all_coins = []

    try:
        best_subset, profit, accuracy_average = find_best_subset()
        selected_coins, total_profit = split_invest_in_subset(best_subset, investment, profit)

        coins_market_info = api_get_response(
            'https://api.coingecko.com/api/v3/coins/markets?vs_currency=USD&order=market_cap_desc&per_page=60&page=1'
            '&sparkline=false'
        )

        print("API Response for /invest:", coins_market_info)

        if not isinstance(coins_market_info, list):
            raise ValueError("Unexpected API response format")

        for coin_info in coins_market_info:
            symbol = coin_info.get('symbol', '').upper()
            if symbol in selected_coins:
                coin_info.update(selected_coins[symbol])
                all_coins.append(coin_info)

        return jsonify({'coins': all_coins, 'profit': total_profit, 'accuracy': accuracy_average})

    except Exception as e:
        app.logger.error(f"Error in /invest endpoint: {str(e)}")
        return jsonify({"error": "An error occurred while processing your request."}), 500


@app.route('/single_coin')
def single_coin():
    coin_id = request.args.get('coin_id')

    try:
        response = api_get_response(f'https://api.coingecko.com/api/v3/coins/{coin_id}')
        if not isinstance(response, dict) or 'symbol' not in response:
            return jsonify({"error": "Symbol not found in the API response."}), 500

        symbol = response.get('symbol', '').upper()

        if symbol not in coins:
            return jsonify({"error": f"Coin data for {symbol} not found."}), 500

        return jsonify({
            'coin': response,
            'start': coins[symbol].get('start_date'),
            'end': coins[symbol].get('end_date'),
            'accuracy': coins[symbol].get('accuracy')
        })

    except Exception as e:
        app.logger.error(f"Error in /single_coin endpoint: {str(e)}")
        return jsonify({"error": "An error occurred while processing your request."}), 500


@app.route('/coin_chart')
def coin_chart():
    coin_id = request.args.get('coin_id')
    symbol = request.args.get('symbol', '').upper()

    try:
        response = api_get_response(
            f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=USD&days=100'
        )

        if not isinstance(response, dict) or 'prices' not in response:
            return jsonify({"error": "Prices data not found in API response."}), 500

        historical = response['prices'][10:-1]
        prediction = predict_next_7_days(symbol, historical)

        coins[symbol]['prediction'] = prediction

        return jsonify({
            'historical': historical,
            'prediction': prediction
        })

    except Exception as e:
        app.logger.error(f"Error in /coin_chart endpoint: {str(e)}")
        return jsonify({"error": "Failed to fetch market data or predict prices."}), 500


@app.route('/trending_coins')
def trending_coins():
    try:
        response = api_get_response(
            'https://api.coingecko.com/api/v3/coins/markets?vs_currency=USD&order=gecko_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h'
        )

        if not isinstance(response, list):
            raise ValueError("Unexpected API response format")

        trending = [coin for coin in response if coin.get('symbol', '').upper() in coins]

        return jsonify({'data': trending})

    except Exception as e:
        app.logger.error(f"Error in /trending_coins endpoint: {str(e)}")
        return jsonify({"error": "Failed to fetch trending coins."}), 500


if __name__ == '__main__':
    scheduler.add_job(update_coins_predictions, 'cron', day_of_week='mon-sun', hour=0, minute=0)
    scheduler.start()
    app.run(debug=True)
