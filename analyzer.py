"""
Analyzer for running analysis on given data models :)

Hopefully all the methods in here will be uses for analyzing the data. If that
stops being true and if I were a good developer (it wouldn't have happened in
the first place) I would update this documentation.
"""
import operator

import time
from collections import defaultdict

import printer
from poloniex_apis import public_api
from poloniex_apis import trading_api
from poloniex_apis.api_models.balances import Balances
from poloniex_apis.api_models.deposit_withdrawal_history import DWHistory
from poloniex_apis.api_models.lending_history import LendingHistory
from poloniex_apis.api_models.ticker_price import TickerData
from poloniex_apis.api_models.trade_history import TradeHistory
from poloniex_apis.public_api import return_usd_btc


def get_overview():
    balances = Balances()
    dw_history = DWHistory(trading_api.return_deposits_withdrawals())
    deposits, withdrawals = dw_history.get_dw_history()
    printer.print_dw_history(deposits, withdrawals)
    balance = dw_history.get_btc_balance(TickerData())
    current = balances.get_btc_total()
    usd_btc_price = return_usd_btc()
    balance_percentage = float("{:.4}".format(current / balance * 100))
    btc_balance_sum = current - balance
    usd_balance_sum = "{:.2f}".format(btc_balance_sum * usd_btc_price)

    printer.print_get_overview_results(
        btc_balance_sum=btc_balance_sum,
        usd_balance_sum=usd_balance_sum,
        balance_percentage=balance_percentage
    )


def get_detailed_overview():
    global current
    ticker_data = TickerData()
    trade_history = trading_api.return_trade_history()
    print("Warning! If you made non BTC trades, for example, ETH to ETC, some")
    print("of the values may look unusual. Since non BTC trades have not been")
    print("calculated in.")
    for ticker in trade_history:
        if ticker.startswith("BTC_"):
            current = list(reversed(trade_history[ticker]))
            btc_sum = 0
            for trade in current:
                if trade['type'] == 'buy':
                    btc_sum += float(trade["total"])
                else:
                    # For some reason, the total for sells do not include the
                    # fee so we include it here.
                    btc_sum -= (float(trade["total"]) * (1 - float(trade["fee"])))

            ticker_sum = 0
            for trade in current:
                if trade['type'] == 'buy':
                    ticker_sum += float(trade["amount"])  # Total
                    ticker_sum -= float(trade["amount"]) * float(trade["fee"])  # Fee
                else:
                    ticker_sum -= float(trade["amount"])
            if ticker_sum > -1:  # Set to 0.000001 to hide 0 balances
                current_btc_sum = float(ticker_data.get_price(ticker)) * ticker_sum
                total_btc = current_btc_sum - btc_sum
                total_usd = float("{:.4}".format(total_btc * ticker_data.get_price("USDT_BTC")))
                print("--------------{}----------------".format(ticker))
                print("Over your account's lifetime, you have invested {} BTC".format(btc_sum))
                print("to achieve your current balance of {} {}/{} BTC".format(ticker_sum, ticker.split("_")[1], current_btc_sum))
                print("If you sold it all at the current price (assuming enough sell orders)")

                if total_btc < 0:
                    print(printer.bcolors.RED, end=' ')
                else:
                    print(printer.bcolors.GREEN, end=' ')
                print("{} BTC/{} USD".format(total_btc, total_usd))
                print(printer.bcolors.END_COLOR, end=' ')

    return current


def calculate_fees():
    # TODO Should this take in the data models or call it itself
    trade_history = TradeHistory(trading_api.return_trade_history())
    all_fees = trade_history.get_all_fees()
    all_prices = public_api.return_ticker()

    fee_dict = defaultdict(float)
    print("--------------All Fees--------------")
    for currency_pair, fees in all_fees.items():
        print("{}={}".format(currency_pair, fees))
        base_currency = currency_pair.split("_")[0]
        fee_dict[base_currency] += fees

    total_fees = 0
    print("-------------Total Fees-------------")
    for currency, fees in fee_dict.items():
        if currency != "BTC":
            if currency == "USDT":
                total_fees += float(all_prices["USDT_BTC"]['last']) * fees
            else:
                total_fees += float(all_prices["BTC_" + currency]['last']) * fees
        else:
            total_fees += fees
    print("Total fees in BTC={}".format(total_fees))


def get_change_over_time():
    """
    Returns a list of currencies whose volume is over the threshold.
    :return:
    """
    threshold = 1000
    currency_list = []

    volume_data = public_api.return_24_hour_volume()
    for item in volume_data:
        if item.startswith('BTC'):
            if float(volume_data.get(item).get('BTC')) > threshold:
                currency_list.append(item)

    currencies = {}
    for currency_pair in currency_list:
        currencies[currency_pair] = float(volume_data.get(currency_pair).get(u'BTC'))
    sorted_currencies = sorted(currencies.items(), key=operator.itemgetter(1), reverse=True)

    period = 300

    time_segments = [3600, 86400, 172800, 259200, 345600, 604800]

    print("Change over time for BTC traded currencies with volume > 1000 BTC")
    for currency in sorted_currencies:
        now = int(time.time())
        last_week = now - 604800
        history = public_api.return_chart_data(
            period=period,
            currency_pair=currency[0],
            start=last_week,
        )
        time_segment_changes = []
        for segment in time_segments:
            try:
                time_segment_changes.append(
                    _to_percent_change(history[-1]['close']/
                                       history[-int((segment/period-1))]['close']))
            except KeyError:
                time_segment_changes.append("No data")

        print("Currency: {}, Volume: {}".format(currency[0], currency[1]))
        print("  1H: {}, 24H: {}, 2D: {}, 3D: {}, 4D: {}, 1W: {}".format(*time_segment_changes))
        time.sleep(2)


def get_lending_history():
    lending_history = LendingHistory()
    data = {}
    for loan in lending_history.history:
        if not loan['currency'] in data:
            data[loan['currency']] = defaultdict()
            data[loan['currency']]['earnings'] = 0
            data[loan['currency']]['fees'] = 0
            data[loan['currency']]['amount'] = 0
            data[loan['currency']]['duration'] = 0
            data[loan['currency']]['weighted_rate'] = 0

        data[loan['currency']]['earnings'] += float(loan['earned'])
        data[loan['currency']]['fees'] += float(loan['fee'])
        data[loan['currency']]['amount'] += float(loan['amount'])
        data[loan['currency']]['duration'] += float(loan['duration'])
        data[loan['currency']]['weighted_rate'] += float(loan['rate'])*float(loan['duration'])

    for currency in data:
        average_rate = float("{:.4}".format(data[currency]['weighted_rate']/data[currency]['duration'] * 100))
        printer.print_get_lending_history(
            currency=currency,
            earnings=data[currency]['earnings'],
            fees=data[currency]['fees'],
            average_rate=average_rate
        )


def _to_percent_change(number):
    if not isinstance(number, float):
        number = float(number)
    return "{:.2f}%".format(number * 100 - 100)



