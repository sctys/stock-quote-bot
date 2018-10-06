import asyncio
import aiohttp
import logging
import os
import json
from logging.handlers import TimedRotatingFileHandler
from bs4 import BeautifulSoup


class StockScrapper(object):

    def __init__(self):
        self.hk_stock_url = 'http://www.aastocks.com/tc/mobile/Quote.aspx?symbol='
        self.us_stock_url = ['https://www.nasdaq.com/en/symbol/', '/real-time']
        self.forex_url = ['http://forex.1forge.com/1.0.3/quotes?pairs=', '&api_key=']
        self.__one_forge_api = os.environ['ONEFORGE_API']
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        logger_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        filelog = TimedRotatingFileHandler('stock_quote_bot.log', when='D', interval=7, backupCount=1)
        filelog.setFormatter(logger_formatter)
        self.logger.addHandler(filelog)
        stdlog = logging.StreamHandler()
        stdlog.setFormatter(logger_formatter)
        self.logger.addHandler(stdlog)

    async def html_page_load(self, url, check_token):
        count = 0
        page = None
        while count < 10 and page is None:
            try:
                self.logger.debug('Start loading page: %s' % url)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            page = None
                            self.logger.error('%s response error.' % url)
                        else:
                            page = await response.read()
                            soup = BeautifulSoup(page, 'html.parser')
                            if len(soup.select(check_token)) == 0:
                                self.logger.error('%s html structure invalid.' % url)
                                page = None
                            else:
                                self.logger.debug('%s loaded.' % url)
                                return page, soup
            except Exception as e:
                page = None
                self.logger.error('%s Unable to load. %s' % (url, e))
            count += 1
        return None, None

    async def forex_api_fetch(self, url):
        count = 0
        page = None
        while count < 10 and page is None:
            try:
                self.logger.debug('Start loading API:')
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            page = None
                            self.logger.error('API response error.')
                        else:
                            page = json.loads(await response.read())
                            self.logger.debug('API loaded.')
                            return page
            except Exception as e:
                page = None
                self.logger.error('API Unable to load. %s' % e)
            count += 1
        return None

    async def hk_stock_scrapper(self, symbol):
        url = self.hk_stock_url + str(symbol)
        page, soup = await self.html_page_load(url, 'table.quote_table')
        if page is not None:
            quote = soup.select('table.quote_table')[0].select('td.two.bottom.right.cell_last')[0].select('div')
            quote = [x.get_text().replace('\r', '').replace('\n', '').strip() for x in quote]
            quote = ','.join(quote[1:3])
        else:
            quote = 'Not available'
        self.logger.debug('Scrapper quote for %s: %s' % (symbol, quote))
        return {symbol: quote}

    async def us_stock_scrapper(self, symbol):
        url = symbol.lower().join(self.us_stock_url)
        page, soup = await self.html_page_load(url, 'div#qwidget_lastsale')
        if page is not None:
            last_price = soup.select('div#qwidget_lastsale')[0].get_text().replace('$', '')
            net_change = soup.select('div#qwidget_netchange')[0]
            if net_change['class'][-1].split('-')[-1] == 'Red':
                sign = '-'
            else:
                sign = ''
            net_change = sign + net_change.get_text()
            per_change = '(' + sign + soup.select('div#qwidget_percent')[0].get_text() + ')'
            quote = last_price + ',' + net_change + per_change
        else:
            quote = 'Not available'
        self.logger.debug('Scrapper quote for %s: %s' % (symbol, quote))
        return {symbol: quote}

    async def forex_api(self, symbol_list):
        symbols = [x.replace('/', '').upper() for x in symbol_list]
        symbol_map = {x: y for x, y in zip(symbols, symbol_list)}
        url = ','.join(symbols).join(self.forex_url) + self.__one_forge_api
        page = await self.forex_api_fetch(url)
        if page is not None:
            quotes = [{symbol_map[x['symbol']]: str(x['price'])} for x in page]
        else:
            quotes = [{x: 'Not available'} for x in symbol_list]
        list(map(lambda a, b: self.logger.debug('API quotes for %s: %s' % (a, b)),
                 [list(x.keys())[0] for x in quotes], [list(x.values())[0] for x in quotes]))
        return [{list(x.keys())[0]: list(x.values())[0]} for x in quotes]

    def report_quote(self, symbols):
        hksymbols = [str(x) for x in symbols if str(x).isdigit()]
        ussymbols = [str(x) for x in symbols if not str(x).isdigit() and '/' not in str(x)]
        forex_symbols = [str(x) for x in symbols if not str(x).isdigit() and '/' in str(x)]
        tasks = [asyncio.ensure_future(self.hk_stock_scrapper(x)) for x in hksymbols] + [
                asyncio.ensure_future(self.us_stock_scrapper(x)) for x in ussymbols]
        api_task = [asyncio.ensure_future(self.forex_api(forex_symbols))] if len(forex_symbols) > 0 else []
        tasks += api_task
        quotes = self.loop.run_until_complete(asyncio.gather(*tasks))
        quotes = [[x] if not isinstance(x, list) else x for x in quotes]
        quotes = [y for x in quotes for y in x]
        return quotes


def main():
    stock = StockScrapper()
    quotes = stock.report_quote([3, 10, 700, 2318, 'AAPL', 'AMZN', 'NVDA', 'EUR/USD', 'USD/JPY', 'XAU/USD', 'BTC/USD',
                                 'BTC/ETH'])
    # quotes = stock.report_quote([3, 10, 700, 2318, 'AAPL', 'AMZN', 'NVDA'])
    print(quotes)


if __name__ == '__main__':
    main()





