import csv
import websocket, json, pprint, numpy, talib
from binance.enums import *
from binance.client import Client
import config
import datetime
import pandas as pd
from decimal import Decimal as D
import pytz
from inputimeout import inputimeout, TimeoutOccurred

tz = pytz.timezone('Europe/Budapest') # choose your timezone
client = Client(config.API_KEY, config.SECRET_KEY)
SOCKET = config.SOCKET # paste your ws setup here
TRADE_SYMBOL = config.TRADE_SYMBOL # 'paste your trading symbol here'

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
# TRADE_QUANTITY = 0.084 #hard coding it may produce errors
MIN_TRADING_USD = 10.3 # rule by binance
ORDER_DATA = ''
fee = 0.001
last_buy = 0 # set 0
n_of_runs = 0
sl_change = None # to track if there was a change for stop loss
closes = []


def save_exception(e,string):
    with open('exception_log.txt','a') as ex:
        print(f'{datetime.datetime.now(tz)} Exception have been raised when {string}, exception: {e}', file=ex)
        print(f'{datetime.datetime.now(tz)} Exception have been raised when {string}, exception: {e}')


def is_interrupted():
    # checks if the previous cycle was interrupted
    global n_of_runs, in_position
    if get_current_pos():
        if n_of_runs == 0:
            n_of_runs += 1
            print('The last cycle was interrupted!')
            return True
    return False


def is_stop_l_active():
    # reads from file whether stop loss active or not,
    # can control stop loss when the program is running already
    global sl_change
    try:
        sl_file = open('stop_loss.txt','r')
        sl = bool(int(sl_file.read()))
        sl_file.close()
        if sl_change != sl:
            sl_change = sl
            if sl:
                print(f'Stop loss is ACTIVATED!')
            else:
                print(f'Stop loss is NOT active!')
        return sl
    except Exception as e:
        save_exception(e,'loading stop loss data')


def get_min_trade_quant(TRADE_SYMBOL, MIN_TRADING_USD):
    # this function returns the lowest possible settable trading quantity
    info = client.get_symbol_info(symbol=TRADE_SYMBOL)
    price_filter = float(info['filters'][0]['tickSize'])
    ticker = client.get_symbol_ticker(symbol=TRADE_SYMBOL)
    price = float(ticker['price'])
    price = D.from_float(price).quantize(D(str(price_filter)))
    minimum = float(info['filters'][2]['minQty']) # 'minQty'
    min_quant = 1/(float(price)/MIN_TRADING_USD)
    TRADE_QUANTITY = D.from_float(min_quant).quantize(D(str(minimum)))
    if is_interrupted():
        lb = get_last_buy_quantity() # change to quantity needed
        if lb > TRADE_QUANTITY:
            TRADE_QUANTITY = lb
    print(f'actual trading quantity {TRADE_QUANTITY}')
    return float(TRADE_QUANTITY)


def get_current_pos():
    # checks what is the actual position, if True a successful buy order was done before
    try:
        with open('current_pos.txt', 'r') as current_pos_file:
            current_pos = bool(int(current_pos_file.read()))
            print(f'my position is: {current_pos}')
            return current_pos
    except FileNotFoundError:
        print("The current_pos file does not exist!")


def get_last_buy_in_usd():
    # loads the last buy order, mainly used to calculate differences
    try:
        with open('order_log.csv', 'r') as order_file:
            for line in reversed(list(csv.reader(order_file))):
                if line[6] == 'BUY':
                    print(f'last buy transactions data have been loaded: {line[5]}')
                    buy_in_usd = line[5]
                    break
        return float(buy_in_usd)
    except Exception as e:
        save_exception(e,'getting last buy data')
        return 0


def get_last_buy_quantity():
    # loads the last buy order's quantity
    try:
        with open('order_log.csv', 'r') as order_file:
            for line in reversed(list(csv.reader(order_file))):
                if line[6] == 'BUY':
                    print(f'last buy transactions data (quantity) have been loaded: {line[1]}')
                    buy_quantity = line[1]
                    break
        return float(buy_quantity)
    except Exception as e:
        with open('exception_log.txt','a') as exc:
            print(f"An exception has occurred when getting last buy data, will return 0. exception: - {e} at "
                  f"{datetime.datetime.now()}",file=exc)
        return 0


def save_current_pos(x):
    # after a successful order was made, the function will save the actual position
    try:
        with open('current_pos.txt', 'w') as current_pos:
            current_pos.write(str(x))
    except Exception as e:
        save_exception(e, 'saving current position')


def check_trade_quant(TRADE_QUANTITY):
    # checks if the actual trade quantity has to be modified in order to make the oncoming order successful
    tmp = get_min_trade_quant(TRADE_SYMBOL=TRADE_SYMBOL, MIN_TRADING_USD=MIN_TRADING_USD)
    if TRADE_QUANTITY < tmp:
        TRADE_QUANTITY = tmp
        print(f'The trade quantity was modified to: {tmp} in order to pass the minimum trading quantity in USD')
    return TRADE_QUANTITY


def order_log(order):
    # logs every successful order to a csv file
    df = pd.DataFrame.from_dict(order)
    df.to_csv('order_log.csv', mode='a', index=False, header=False)


def order(side, quantity, symbol, order_type=ORDER_TYPE_MARKET):
    # creates and order and saves its details while printing it.
    global ORDER_DATA
    try:
        print("Sending Order")
        order = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        try:
            ORDER_DATA = order['fills']
            ORDER_DATA = ORDER_DATA[0]
            ORDER_DATA['cummulativeQuoteQty'] = [order['cummulativeQuoteQty']]
            ORDER_DATA['side'] = order['side']
            ORDER_DATA['symbol'] = order['symbol']
            ORDER_DATA['date'] = datetime.datetime.now(tz)
            pprint.pprint(ORDER_DATA)
            order_log(ORDER_DATA)
        except Exception as e:
            save_exception(e,'generating and saving order data')
    except Exception as e:
        save_exception(e,'sending order')
        return False
    return True


def store_message(json_message):
    # function to store received messages, greyed out by default
    try:
        df = pd.DataFrame.from_records(json_message, index=['k'])
        df['dates'] = datetime.datetime.now(tz)
        df.to_csv('stored_messages.csv', mode='a', index=True, header=False)
    except Exception as e:
        print("An exception has occurred when storing messages, exception: {}".format(e))


def store_closes(row):
    # a function to store every candle closes accompanied by RSI data and transaction data, for future evaluation
    try:
        df = pd.DataFrame.from_dict(row)
        df.to_csv('close_log.csv', mode='a', index=False, header=False)
    except Exception as e:
        save_exception(e,'storing closes')


def store_successful_trans_log(row):
    # a function to store only the successful transactions for future evaluation
    try:
        df = pd.DataFrame.from_dict(row)
        df.to_csv('strans_log.csv', mode='a', index=False, header=False)
        print('transaction has been stored successfully!')
    except Exception as e:
        save_exception(e,'storing transactions')


def stop_loss(close):
    # if the current price gets below the purchase price its execute a sell order
    # still figuring out the correct implementation, as the trading algo is quite simple
    # it might stop early just before a rebound, thus generating extra charges,
    # but takes away any possible potential income
    global in_position, last_buy, closes, TRADE_QUANTITY
    print(f'check for stop loss, buying price: {last_buy} new price {close}')
    if last_buy - 0.5 > close and in_position:
        print('******** SELL ********')
        order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, TRADE_SYMBOL)
        if order_succeeded:
            in_position = 0
            save_current_pos(in_position)
            tls = closes
            tls.append(close)
            np_closes = numpy.array(tls)
            rsi = talib.RSI(np_closes, RSI_PERIOD)
            last_rsi = rsi[-1]
            sell_in_usd = close * TRADE_QUANTITY * (1 - fee)
            print('stop loss function successfully issued an emergency SELL order')
            row = {'dates': datetime.datetime.now(tz), 'closes': [close], 'RSI': [last_rsi], 'transaction': [sell_in_usd]}
            buy_in_usd = get_last_buy_in_usd()
            row['difference'] = [sell_in_usd - buy_in_usd]
            store_successful_trans_log(row)


def on_open(ws):
    print("opened connection, Press CTRL + C to stop the bot at any time, dont forget to hit an ENTER when needed, "
          "otherwise it will timeout and try to run again!")


def on_close(ws):
    print(f"Closed connection at:\n {datetime.datetime.now(tz)}")


def on_message(ws, message):
    global closes, in_position, TRADE_QUANTITY, last_buy
    print("Received message")
    with open('message.txt','a') as message_file:
        print(message,file=message_file)
    json_message = json.loads(message)
    candle = json_message['k']
    # store_message(candle)
    # pprint.pprint(json_message)
    is_candle_closed = candle['x']
    close = float(candle['c'])
    if in_position:
        if is_stop_l_active():
            stop_loss(close)
    if is_candle_closed:
        # store_message(candle)
        print("candle has closed at: {}".format(close))
        closes.append(close)

        if len(closes) > RSI_PERIOD:
            np_closes = numpy.array(closes)
            rsi = talib.RSI(np_closes, RSI_PERIOD)
            print("all RSIs have been calculated:")
            print(rsi)
            last_rsi = rsi[-1]
            print(f'Current RSI: \n{last_rsi}')
            row = {'dates': datetime.datetime.now(tz) ,
                   'closes': [close],
                   'RSI': [last_rsi],
                   'transaction': [0],
                   'difference': [0]}

            if last_rsi < RSI_OVERSOLD:
                if in_position:
                    print("It is oversold, but we own")
                    with open('attempt_log.txt', 'a') as attempt:
                        print(f'{datetime.datetime.now(tz)} It is oversold, but we own', file=attempt)
                else:
                    print("********* BUY ********")
                    TRADE_QUANTITY = check_trade_quant(TRADE_QUANTITY)
                    order_succeeded = order(SIDE_BUY, TRADE_QUANTITY, TRADE_SYMBOL)
                    if order_succeeded:
                        try:
                            in_position = 1
                        except Exception as e:
                            save_exception(e,'setting position')
                        save_current_pos(in_position)
                        try:
                            last_buy = close
                            buy_in_usd = close * TRADE_QUANTITY + (close * TRADE_QUANTITY * fee)
                            row['transaction'] = [buy_in_usd * -1]
                        except Exception as e:
                            save_exception(e,'gathering order data')
                        store_successful_trans_log(row)

            if last_rsi > RSI_OVERBOUGHT:
                if in_position:
                    print('******** SELL ********')
                    TRADE_QUANTITY = check_trade_quant(TRADE_QUANTITY)
                    order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, TRADE_SYMBOL)
                    if order_succeeded:
                        try:
                            in_position = 0
                        except Exception as e:
                            save_exception(e, 'setting position')
                        save_current_pos(in_position)
                        try:
                            sell_in_usd = close * TRADE_QUANTITY * (1 - fee)
                            row['transaction'] = [sell_in_usd]
                            buy_in_usd = get_last_buy_in_usd()
                            row['difference'] = [sell_in_usd - buy_in_usd]
                        except Exception as e:
                            save_exception(e, 'gathering order data')
                        store_successful_trans_log(row)
                else:
                    print("It is overbought, but we dont own any")
                    with open('attempt_log.txt', 'a') as attempt:
                        print(f'{datetime.datetime.now(tz)} It is overbought, but we dont own any', file=attempt)
            store_closes(row)


def main():
    ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
    while True:
        # Press CTRL + C to stop the bot at any time, dont forget to hit an ENTER when needed,
        # otherwise it will timeout and try to run again!
        try:
            ws.run_forever()
        except Exception as e:
            save_exception(e,'connecting to the websocket')
        print("Reconnecting to the websocket  after 5 sec, press ENTER to exit!")
        try:
            c = inputimeout(prompt='>>', timeout=5)
            break
        except TimeoutOccurred:
            c = 'connecting...'
            print(c)


if __name__ == '__main__':
    in_position = get_current_pos()
    TRADE_QUANTITY = get_min_trade_quant(TRADE_SYMBOL, MIN_TRADING_USD)
    main()
