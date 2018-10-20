import aiohttp
import asyncio
import os
import logging
import json
from stock_scrapper import StockScrapper
from logging.handlers import TimedRotatingFileHandler


class TelegramBot(object):

    def __init__(self):
        self.__token = os.environ['TELEGRAM_TOKEN']
        self.endpoint = 'https://api.telegram.org/bot%s' % self.__token
        self.get_message_url = '/getUpdates'
        self.send_message_url = '/sendMessage'
        self.last_update_id = 0
        self.scrapper = StockScrapper()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        logger_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        filelog = TimedRotatingFileHandler('stock_quote_bot.log', when='D', interval=7, backupCount=1)
        filelog.setFormatter(logger_formatter)
        self.logger.addHandler(filelog)
        stdlog = logging.StreamHandler()
        stdlog.setFormatter(logger_formatter)
        self.logger.addHandler(stdlog)

    async def telegram_url(self, url, params=None):
        if self.send_message_url in url:
            send = True
        else:
            send = False
        params = {} if params is None else params
        count = 0
        message = None
        while count < 10 and message is None:
            try:
                if not send:
                    self.logger.debug('Start getting message:')
                else:
                    self.logger.debug('Start sending message:')
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            message = None
                            if not send:
                                self.logger.error('Unable to get message.')
                            else:
                                self.logger.error('Unable to send message.')
                        else:
                            message = json.loads(await response.read())
                            if not send:
                                if message['ok']:
                                    self.logger.debug('Message updated.')
                                    return message
                                else:
                                    message = None
                                    self.logger.error('Message not ok.')
                            else:
                                self.logger.debug('Message sent.')
                                return message
            except Exception as e:
                message = None
                if not send:
                    self.logger.error('Error in getting message. %s' % e)
                else:
                    self.logger.error('Error in sending message. %s' % e)
            count += 1
        return None

    async def get_message(self, offset=0, timeout=300):
        url = self.endpoint + self.get_message_url
        params = {'offset': offset, 'timeout': timeout}
        message = await self.telegram_url(url, params)
        return message

    async def get_last_update_id(self):
        message = await self.get_message()
        if len(message['result']) > 0:
            self.last_update_id = message['result']['update_id'] + 1
        else:
            self.last_update_id = 0

    async def get_unprocessed_message(self):
        message = await self.get_message(offset=self.last_update_id)
        return message['result']

    async def send_message(self, content, user_id):
        url = self.endpoint + self.send_message_url
        params = {'chat_id': user_id, 'text': content}
        await self.telegram_url(url, params)

    async def message_classification(self, message):
        msg_text = message['text']
        if '/ask/price' in msg_text:
            message_type = 'ask_price'
        elif '/nickname' in msg_text:
            if '/add' in msg_text:
                message_type = 'nickname_add'
            elif '/remove' in msg_text:
                message_type = 'nickname_remove'
            else:
                message_type = None
        elif '/watchlist' in msg_text:
            if '/add' in msg_text:
                message_type = 'watchlist_add'
            elif '/remove' in msg_text:
                message_type = 'watchlist_remove'
            else:
                message_type = None
        elif '/position' in msg_text:
            if '/add' in msg_text:
                message_type = 'position_add'
            elif '/manage' in msg_text:
                message_type = 'position_manage'
            else:
                message_type = None
        elif '/notification' in msg_text:
            if '/manage' in msg_text:
                message_type = 'notification_manage'
            elif '/disable' in msg_text:
                message_type = 'notification_disable'
            elif '/enable' in msg_text:
                message_type = 'notification_enable'
            else:
                message_type = None
        else:
            message_type = None
        return message_type

    @staticmethod
    def check_watchlist(user_id):
        watchlist = Watchlist.objects(createdBy=user_id)
        if len(watchlist) > 0:
            return watchlist[0].symbol
        else:
            return None

    @staticmethod
    def check_nickname(user_id, query):
        stock = Stock.objects(Q(nickname=query) & Q(createdBy=user_id))
        if len(stock) > 0:
            return stock[0].symbol
        else:
            return []

    async def ask_price(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/ask/price ')
        # Check if the query_token is watch_list for user
        # If yes, get list of symbol from watch_list
        query = self.check_watchlist(user_id)
        if len(query) == 0:
            query = query_token.split(',').trim()
        # Check if the query_token is nick_name for user
        # If yes, get symbol from nick_name
        # Else, treat query directly as symbol
        symbol = [self.check_nickname(user_id, x) for x in query]
        symbol_dict = {x: y for x, y in zip(symbol, query)}
        asyncio.set_event_loop(self.scrapper.loop)
        quotes = self.scrapper.report_quote(symbol)
        response = '\n'.join(['%s: %s' % (symbol_dict[list(x.keys())[0]], list(x.values())[0]) for x in quotes])
        await self.send_message(response, user_id)

    @staticmethod
    def market_classification(symbol):
        if str(symbol).isdigit():
            market = 'hk'
        elif not str(symbol).isdigit() and '/' not in str(symbol):
            market = 'us'
        elif not str(symbol).isdigit() and '/' in str(symbol):
            market = 'forex'
        else:
            market = 'unknonwn'
        return market

    async def nickname_add(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/nickname/add ')
        symbol, nickname = query_token.split(' ')
        market = self.market_classification(symbol)
        Stock(symbol=symbol, nickname=nickname, createdBy=user_id, market=market).save()
        response = 'New entry added:\nSymbol: %s, NickName: %s, Market: %s' % (symbol, nickname, market)
        await self.send_message(response, user_id)

    async def nickname_remove(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/nickname/remove ').trim()
        Stock.objects(Q(createdBy=user_id) & (Q(symbol=query_token) | Q(nickname=query_token))).delete()
        response = 'Entry removed: %s' % query_token
        await self.send_message(response, user_id)

    async def watchlist_add(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/watchlist/add ').trim()
        new_symbol_list = query_token.split(',')
        old_symbol_list = self.check_watchlist(user_id)
        symbol_list = old_symbol_list + new_symbol_list
        Watchlist(createdBy=user_id, stockSymbols=symbol_list).save()
        response = 'Watchlist added with symbols:\n%s' % ', '.join(new_symbol_list)
        await self.send_message(response, user_id)

    async def watchlist_remove(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/watchlist/remove ').trim()
        del_symbol_list = query_token.split(',')
        old_symbol_list = self.check_watchlist(user_id)
        symbol_list = [x for x in old_symbol_list if x not in del_symbol_list]
        Watchlist(createdBy=user_id, stockSymbols=symbol_list).save()
        response = 'Watchlist removed the symbols:\n%s' % ', '.join(del_symbol_list)
        await self.send_message(response, user_id)

    async def position_add(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/position/add ').trim()











def main():
    tg_bot = TelegramBot()
    print(tg_bot.loop.run_until_complete(tg_bot.get_message()))


if __name__ == '__main__':
    main()



