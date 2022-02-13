# penny-bot
It's a trading bot written in python!
Based on the current RSI its creates buy or sell orders.
To make it work you would need:
 - a binance account, as trading is done on the given platform!
 - when the account is ready, you need to generate an API.
 - when it's done, you have to create a ```config.py``` file which should only contain your API keys like this:
 
 ```API_KEY = "YOUR_API_KEY_PASTED_HERE"```
 
 ```SECRET_KEY = "YOUR_SECRET_KEY_PASTED_HERE"```
 
 - choose your trading currency and set it up in the ```bot.py``` file:
 
 ex.: ```TRADE_SYMBOL = 'BTCUSDT'``` or 'ETHUSDT' any of the many, choose one not that popular but stable.
 
 ex.: ```SOCKET = 'wss://stream.binance.us:9443/ws/btcusdt@kline_1m``` [here is documentation for it](https://github.com/binance-us/binance-official-api-docs/blob/master/web-socket-streams.md#klinecandlestick-streams).
 
 - install all the requirements from the ```requirements.txt```. TA-lib can be dificult to install on Windows, i have bypassed this problem by simply downloading the latest package from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib) and installing by opening the terminal in the containing folder and run the following command (change the package name to your) ```pip install TA_Lib-0.4.19-cp38-cp38-win_amd64.whl``` and it should work now, if no luck till now, here is another more detailed instruction for any OS [click](https://blog.quantinsti.com/install-ta-lib-python/).
 - to run the bot you would also need to top up your binance account with an ammount you ready to loose, at least with the trading minimum which is 10 USD but counting with the fees and price fluctuation, the bot will work with 10.30 USD by default, so start your trading carrier with around 20 USD.
 - the bot was made and published solly for educational purposes only, it's not a financial advice, I'm not responsible if you loose any money! Please be careful when trading!
