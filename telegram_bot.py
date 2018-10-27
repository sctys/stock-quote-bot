import aiohttp
import asyncio
import os
import logging
import json
from stock_scrapper import StockScrapper
from db import *
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
            elif '/list' in msg_text:
                message_type = 'position_list'
            elif '/view' in msg_text:
                message_type = 'position_view'
            elif '/remove' in msg_text:
                message_type = 'position_remove'
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
        users = User.objects(telegramUid=user_id)
        watchlist = Watchlist.objects(createdBy=users[0].id)
        if len(watchlist) > 0:
            return watchlist[0].stockSymbols
        else:
            return None

    @staticmethod
    def check_nickname(user_id, query):
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(nickname=query) & Q(createdBy=users[0].id))
        if len(stock) > 0:
            return stock[0].symbol
        else:
            return query

    async def ask_price(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/ask/price ', '')
        if len(query_token) == 0:
            query = self.check_watchlist(user_id)
        else:
            query = query_token.split(',')
            query = [x.strip() for x in query]
        symbol = [self.check_nickname(user_id, x) for x in query]
        symbol_dict = {x: y for x, y in zip(symbol, query)}
        quotes = await self.scrapper.report_quote(symbol)
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
        query_token = msg_text.replace('/nickname/add ', '')
        symbol, nickname = query_token.split(' ')
        market = self.market_classification(symbol)
        users = User.objects(telegramUid=user_id)
        Stock(symbol=symbol, nickname=nickname, createdBy=users[0].id, market=market).save()
        response = 'New entry added:\nSymbol: %s, NickName: %s, Market: %s' % (symbol, nickname, market)
        await self.send_message(response, user_id)

    async def nickname_remove(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/nickname/remove ', '').strip()
        users = User.objects(telegramUid=user_id)
        Stock.objects(Q(createdBy=users[0].id) & (Q(symbol=query_token) | Q(nickname=query_token))).delete()
        response = 'Entry removed: %s' % query_token
        await self.send_message(response, user_id)

    async def watchlist_add(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/watchlist/add ', '')
        new_symbol_list = query_token.split(',')
        new_symbol_list = [x.strip() for x in new_symbol_list]
        old_symbol_list = self.check_watchlist(user_id)
        symbol_list = list(set(old_symbol_list + new_symbol_list))
        users = User.objects(telegramUid=user_id)
        Watchlist.objects(createdBy=users[0].id).delete()
        Watchlist(createdBy=users[0].id, stockSymbols=symbol_list).save()
        response = 'Watchlist added with symbols:\n%s' % ', '.join(new_symbol_list)
        await self.send_message(response, user_id)

    async def watchlist_remove(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/watchlist/remove ', '')
        del_symbol_list = query_token.split(',')
        del_symbol_list = [x.strip() for x in del_symbol_list]
        old_symbol_list = self.check_watchlist(user_id)
        symbol_list = [x for x in old_symbol_list if x not in del_symbol_list]
        users = User.objects(telegramUid=user_id)
        Watchlist.objects(createdBy=users[0].id).delete()
        Watchlist(createdBy=users[0].id, stockSymbols=symbol_list).save()
        response = 'Watchlist removed the symbols:\n%s' % ', '.join(del_symbol_list)
        await self.send_message(response, user_id)

    async def position_add(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/position/add ', '')
        symbol, buyprice, buyunit = query_token.split(' ')
        symbol = symbol.strip()
        buyprice = buyprice.strip()
        buyunit = buyunit.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=symbol))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=symbol))
        Position(createdBy=users[0].id, stock=stock[0].id, unitPrice=buyprice, quantity=buyunit).save()
        response = 'Position added for %s, unit price = %s, quantity = %s' % (stock[0].symbol, buyprice, buyunit)
        await self.send_message(response, user_id)

    async def position_list(self, message):
        user_id = message['from']['id']
        users = User.objects(telegramUid=user_id)
        position = Position.objects(createdBy=users[0].id)
        position = ['Symbol: %s, Nickname: %s, unit price: %s, quantity: %s' % (
            x.stock.symbol, x.stock.nickname, x.unitPrice, x.quantity) for x in position]
        response = '\n'.join(position)
        await self.send_message(response, user_id)

    async def position_view(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/position/view ', '')
        query = query_token.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        position = Position.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id))
        old_price = position.unitPrice
        quantity = Position.quantity
        new_price = await self.scrapper.report_quote(list(stock.symbol))[0][stock.symbol].split(',')[0]
        profit = (float(new_price) - float(old_price)) * quantity
        percent_profit = str((float(new_price) / float(old_price) - 1) * 100) + '%'
        response = 'Profit = %s, Percent profit = %s' % (profit, percent_profit)
        await self.send_message(response, user_id)














def main():
    tg_bot = TelegramBot()
    print(tg_bot.loop.run_until_complete(tg_bot.get_message()))
    # print(tg_bot.check_watchlist(263664408))
    # asyncio.set_event_loop(tg_bot.loop)
    print(tg_bot.loop.run_until_complete(tg_bot.watchlist_remove({'message_id': 29, 'from': {'id': 263664408, 'is_bot': False, 'first_name': 'SCTYS', 'username': 'sctys', 'language_code': 'en-US'}, 'chat': {'id': 263664408, 'first_name': 'SCTYS', 'username': 'sctys', 'type': 'private'}, 'date': 1540632514, 'text': '/watchlist/remove 66, 821'})))


if __name__ == '__main__':
    main()



