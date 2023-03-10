from datetime import datetime
import calendar
import requests
import time
from pandas import pandas as pd
import logging
from pathlib import Path
from dotenv import load_dotenv
import os, sys

logging.basicConfig(level=logging.INFO)
env = load_dotenv(dotenv_path=Path('config.env'))
if not env:
    logging.error("== NOT LOADED ENVIROMENT\n check your .env ")


chat_id = os.getenv('CHAT_ID')
token = os.getenv('TELEGRAM_TOKEN')


if not(chat_id or token):
    logging.error(" === NOT TELGRAM CHAT_ID OR TOKEN  ===")
    sys.exit()


def validate_list(list_obj,symbol,value):
    ##############################################################
    #  
    # list obj: [1,2,10]
    # symbol: > could be (<, >,=,<=,>=)
    # value: 10
    # Evauluates each of element of list according to symbol
    # 1 > 10, 2 > 10, 10 > 10
    # and returns True of False if is True
    #
    ############################################################## 
    vals = []

    for l in list_obj:
        if symbol == "<":
            vals.append(l < value)
        elif symbol == "<=":
            vals.append(l <= value)
        elif symbol == ">":
            vals.append(l > value)
        elif symbol == ">=":
            vals.append(l >= value)
        elif symbol == "==":
            vals.append(l == value)

    return all(vals)
        

def send_message(message):
    url =  "https://api.telegram.org/bot" + token

    if message:
        send_message = f"/sendMessage?chat_id={chat_id}&text={message}"
        base_url = url + send_message
        return requests.get(base_url)


def get_rsi(symbol="BTCBUSD",timeinterval="4h",period=4,**args):
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
    now = datetime.now().strftime("%H:%M:%S")
    logging.info(f": {now} : { symbol } - { '{:.2f}'.format(df2['close'].iloc[-1])} - RSI: { '{:.10f}'.format(rsi) } - { timeinterval }")
    return float(rsi)

def format_args(arguments):
    if '--h' in arguments:
        print("""\
--------------------------------------------------------------------------------------

                            RSI ALERTS FROM BINANCE

                ARGUMENTS (by default):
                    symbol = "BTC" + "BUSD"
                    timeinterval = "3m"
                    down = 25 # lowest point from RSI to alert
                    up = 75 # highest point from RSI to alert
                    sleep_duration = 60*5 # Seconds to sleep
                    period = 6 # Time period to calculate RSI binace has default 6

                EXAMPLE:

                python rsi_alerts.py "ETHBUSD" "3m" 25 75 300 6

                -- note: you can use a only one argument

                python rsi_alerts.py "DOT" --> trade DOTBUSD with all default vals

--------------------------------------------------------------------------------------""")
        sys.exit()
 
    symbol = "BTC" + "BUSD"
    timeinterval = "3m"
    down = 25 # lowest point from RSI to alert
    up = 75 # highest point from RSI to alert
    sleep_duration = 60*5 # Seconds to sleep
    period = 6 # Time period to calculate RSI binace has default 6

    values = [symbol, timeinterval, down, up, sleep_duration, period]
    
    # Format arguments values 
    arguments.pop(0)
    for num,value in enumerate(arguments):
        if num == 0:
            value = value.upper()
            if "BUSD" not in value:
                value = value + "BUSD"

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
    
    logging.info(f"""
    ==================================================
                Start RSI alerts 

        symbol: {symbol} - currency
        period: { period } - periods to calculate rsi
        timeinterval {timeinterval} - 1m,5m,15m,1h,2h4h
        down : { down } # lowest point from RSI to alert
        up : { down } # highest point from RSI to alert
        sleep_duration : { sleep_duration } # Seconds to sleep
        period: { period }

    ===================================================

    """)

    #    RULES FOR ALERTS ACCORDING AMOUNT OF TIME
    #
    #    15m, 1h and 4h- values up= 70 down= 25
    #
    #    RUNS EVERY 15 MINUTES 


    while True:

        try:
            rsi_15m = get_rsi(symbol=symbol,timeinterval="15m",period=period)
            rsi_1h = get_rsi(symbol=symbol,timeinterval="1h",period=period)
            rsi_4h = get_rsi(symbol=symbol,timeinterval="4h",period=period)

            mark_price = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}").json().get('markPrice','error in script :(')

            alert_message = f"""\
ALERTA DE PRECIO: { symbol }\n
Precio: { mark_price }
RSI 15m: { rsi_15m }
RSI 1h: { rsi_1h }
RSI 4h: { rsi_4h }
Fecha: { datetime.now().strftime('%H:%M:%S %d-%m-%Y') }"""


            if validate_list([rsi_15m,rsi_1h,rsi_4h],"<",down):
                send_message(alert_message + "\n ==== LONG ====")

            elif  validate_list([rsi_15m,rsi_1h,rsi_4h],">",up):
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


