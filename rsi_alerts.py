from datetime import datetime
import calendar
import requests
import time
from pandas import pandas as pd
import logging
from pathlib import Path
from dotenv import load_dotenv
import os, sys
import numpy as np

logging.basicConfig(level=logging.INFO)
env = load_dotenv(dotenv_path=Path('config.env'))
if not env:
    logging.error("== NOT LOADED ENVIROMENT\n check your .env ")


chat_id = os.getenv('CHAT_ID')
token = os.getenv('TELEGRAM_TOKEN')


if not(chat_id or token):
    logging.error(" === NOT TELGRAM CHAT_ID OR TOKEN  ===")
    sys.exit()


def get_data(symbol="BTCUSDT",timeinterval="4h",limit=50):
    url = 'https://fapi.binance.com/fapi/v1/klines?symbol='+symbol+'&interval='+timeinterval+'&limit='+str(limit)
    data = requests.get(url).json()
    return data

def get_bollinger_bands(data, period=20, std_dev_factor=2):
    # FOR DEFAULT PERIOD = 21, STD_DEV_FACTOR = 2
    closing_prices = [float(entry[4]) for entry in data]
    rolling_mean = np.mean(closing_prices[-period:])
    rolling_std = np.std(closing_prices[-period:])
    upper_band = rolling_mean + std_dev_factor * rolling_std
    middle_band = rolling_mean
    lower_band = rolling_mean - std_dev_factor * rolling_std
    return upper_band, middle_band, lower_band
        

def send_message(message):
    url =  "https://api.telegram.org/bot" + token

    if message:
        send_message = f"/sendMessage?chat_id={chat_id}&text={message}"
        base_url = url + send_message
        return requests.get(base_url)


def get_rsi(symbol="BTCUSDT",timeinterval="4h",period=4,**args):
    now = datetime.utcnow()
    unixtime = calendar.timegm(now.utctimetuple())
    since = unixtime
    start=str(since-60*60*10)    
    url = 'https://fapi.binance.com/fapi/v1/klines?symbol='+symbol+'&interval='+timeinterval+'&limit=100'
    data = requests.get(url).json()        
    
    D = pd.DataFrame(data)
    D.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades',
                 'taker_base_vol', 'taker_quote_vol', 'is_best_match']
    
    df=D
    df['close'] = df['close'].astype(float)
    df2=df['close'].to_numpy()
    
    df2 = pd.DataFrame(df2, columns = ['close'])
    delta = df2.diff()
    
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    
    RS = _gain / _loss
    
    
    rsi=100 - (100 / (1 + RS))
    rsi=rsi['close'].iloc[-1]
   
    return float(rsi)

def format_args(arguments):
    if '--h' in arguments:
        print("""\
--------------------------------------------------------------------------------------

                            RSI ALERTS FROM BINANCE

                ARGUMENTS (by default):
                    symbol = "BTC" + "USDT"
                    timeinterval = "3m"
                    down = 25 # lowest point from RSI to alert
                    up = 75 # highest point from RSI to alert
                    sleep_duration = 60*5 # Seconds to sleep
                    period = 6 # Time period to calculate RSI binace has default 6

                EXAMPLE:

                python rsi_alerts.py "ETHUSDT" "3m" 25 75 300 6

                -- note: you can use a only one argument

                

--------------------------------------------------------------------------------------""")
        sys.exit()
 
    symbol = "BTC" + "USDT"
    timeinterval = "4h"
    down = 30 # lowest point from RSI to alert
    up = 70 # highest point from RSI to alert
    sleep_duration = 60*2 # Seconds to sleep
    period = 6 # Time period to calculate RSI binace has default 6

    values = [symbol, timeinterval, down, up, sleep_duration, period]
    
    # Format arguments values 
    arguments.pop(0)
    for num,value in enumerate(arguments):
        if num == 0:
            value = value.upper()
            if "USDT" not in value:
                value = value + "USDT"

        values[num] = value

    symbol = values[0]
    timeinterval = values[1]
    down = values[2]
    up = values[3]
    sleep_duration = values[4]
    period = values[5]

    return symbol, timeinterval, down, up, sleep_duration, period


def main():
    symbol, timeinterval, down, up, sleep_duration, period = format_args(sys.argv)
    BOLL_PERIOD = 5
    BOLL_STD_DEV_FACTOR = 2.1

    
    logging.info(f"""
    ==================================================
                Start RSI/BOLL alerts 

        symbol: {symbol} - currency
        period: { period } - periods to calculate rsi
        timeinterval {timeinterval} - 1m,5m,15m,12h,2h,4h
        down : { down } # lowest point from RSI to alert
        up : { up } # highest point from RSI to alert
        sleep_duration : { sleep_duration } # Seconds to sleep
        period: { period }
        BOLL_PERIOD: { BOLL_PERIOD }
        BOLL_STD_DEV_FACTOR: { BOLL_STD_DEV_FACTOR }

    ===================================================

    """)


    while True:

        try:
            data = get_data(symbol=symbol, timeinterval=timeinterval,limit=27)
            upper_band, middle_band, lower_band = get_bollinger_bands(data, period=BOLL_PERIOD, std_dev_factor=BOLL_STD_DEV_FACTOR)
            upper_band =  '{:.2f}'.format(float(upper_band))
            middle_band =  '{:.2f}'.format(float(middle_band))
            lower_band =  '{:.2f}'.format(float(lower_band))

            rsi = get_rsi(symbol=symbol,timeinterval=timeinterval,period=period)

            mark_price = '{:.2f}'.format(float(requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}").json().get('markPrice','error in script :(')))


            alert_message = f"""\
ALERTA DE PRECIO: { symbol }\n
Precio: { mark_price }
RSI {timeinterval}: { rsi }
upper: { upper_band }
middle: { middle_band }
lower: { lower_band }
Fecha: { datetime.now().strftime('%H:%M:%S %d-%m-%Y') }"""

            now = datetime.now().strftime("%H:%M:%S")
            logging.info(f": {now} : { symbol } - { mark_price } - RSI: { '{:.2f}'.format(rsi) } - { timeinterval } | {upper_band} | {middle_band} | {lower_band} |")

            if rsi < down and mark_price >= upper_band:
                send_message(alert_message + "\n ==== LONG ====")

            elif rsi > up and mark_price <= lower_band:
                send_message(alert_message + "\n ==== SHORT ====")


            time.sleep(sleep_duration)
        except Exception as error:
            logging.error(f"Error on rsi code: { error }")
            send_message(f"Error on server: \n{ error }")
            logging.info(": : sleep for 30 seconds and retry : :")
            time.sleep(30)
            continue





if __name__ == "__main__":
    main()


