from flask import Flask
from flask import request
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
    investment = request.json.get('investment')
    all_coins = []

    best_subset, profit, accuracy_average = find_best_subset()
    coins, total_profit = split_invest_in_subset(
        best_subset, investment, profit)
    try:
        coins_market_info = api_get_response(f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=USD&order'
                                             f'=market_cap_desc&per_page=60&page=1&sparkline=false')
    except Exception as e:
        coins_market_info = None

    try:
        for i in range(len(coins_market_info)):
            symbol = coins_market_info[i]['symbol'].upper()
            if symbol in coins:
                coins_market_info[i].update(coins[symbol])
                all_coins.append(coins_market_info[i])
    except Exception as e:
        pass

    return {'coins': all_coins, 'profit': total_profit, 'accuracy': accuracy_average}


@app.route('/single_coin')
def single_coin():
    coin_id = request.args.get('coin_id')
    response = api_get_response(f'https://api.coingecko.com/api/v3/coins/{coin_id}')
    if 'symbol' not in response:
        return {"error": "Symbol not found in the API response."}, 500

    symbol = response['symbol'].upper()

    if symbol not in coins:
        return {"error": f"Coin data for {symbol} not found."}, 500

    return {
        'coin': response,
        'start': coins[symbol]['start_date'],
        'end': coins[symbol]['end_date'],
        'accuracy': coins[symbol]['accuracy']
    }


@app.route('/coin_chart')
def coin_chart():
    coin_id = request.args.get('coin_id')
    symbol = request.args.get('symbol').upper()

    try:
        response = api_get_response(
            f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=USD&days=100')
    except Exception as e:
        return {"error": f"Failed to fetch market data: {str(e)}"}, 500

    if 'prices' in response:
        historical = response['prices'][10:-1]
        try:
            prediction = predict_next_7_days(symbol, historical)
        except Exception as e:
            return {"error": f"Failed to predict prices: {str(e)}"}, 500

        coins[symbol]['prediction'] = prediction
        return {
            'historical': historical,
            'prediction': prediction
        }
    else:
        return {"error": "Prices data not found in API response."}, 500


@app.route('/trending_coins')
def trending_coins():
    response = api_get_response(
        'https://api.coingecko.com/api/v3/coins/markets?vs_currency=USD&order=gecko_desc&per_page'
        '=10&page=1&sparkline=false&price_change_percentage=24h')
    trending = []
    try:
        for coin in response:
            if coin['symbol'].upper() in coins:
                trending.append(coin)
    except Exception as e:
        pass
    return {'data': trending}


if __name__ == '__main__':
    scheduler.add_job(update_coins_predictions, 'cron',
                      day_of_week='mon-sun', hour=00, minute=00)
    scheduler.start()
    app.run(debug=True)


