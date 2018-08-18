import asyncio
import aiohttp
from bs4 import BeautifulSoup


class StockScrapper(object):

    def __init__(self):
        self.hk_stock_url = 'http://www.aastocks.com/tc/mobile/Quote.aspx?symbol='

    async def hk_stock_scrapper(self, symbol):
        url = self.hk_stock_url + str(symbol)
        count = 0
        page = None
        while count < 10 and page is None:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            page = None
                        else:
                            page = await response.read()
                            soup = BeautifulSoup(page, 'html.parser')
                            if len(soup.select('table.quote_table')) == 0:
                                page = None
            except Exception:
                page = None
            count += 1
        if page is not None:
            quote = soup.select('table.quote_table')[0].select('td.two.bottom.right.cell_last')[0].select('div')
            quote = [x.get_text().replace('\r', '').replace('\n', '').strip() for x in quote]
            quote = ','.join(quote[1:3])
        else:
            quote = 'Not available'
        return {symbol: quote}

    def report_quote(self, symbols):
        hksymbols = [str(x) for x in symbols if str(x).isdigit()]
        loop = asyncio.get_event_loop()
        tasks = [asyncio.ensure_future(self.hk_stock_scrapper(x)) for x in hksymbols]
        quotes = loop.run_until_complete(asyncio.gather(*tasks))
        return quotes


def main():
    stock = StockScrapper()
    quotes = stock.report_quote([3, 10, 700, 2318])
    print(quotes)


if __name__ == '__main__':
    main()





