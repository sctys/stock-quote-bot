import aiohttp
import asyncio
import os
import logging
import json
from stock_scrapper import StockScrapper
from db import *
from logging.handlers import TimedRotatingFileHandler
import telegram
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

class TelegramBot(object):

    def __init__(self):
        self.updater = Updater(token=os.environ['TELEGRAM_TOKEN'])
        self.dispatcher = self.updater.dispatcher
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

    # Default helper message response.
    def help_message_handler(self, bot, update):
        response = '\n'.join([
            'Support commands:',
            '`/ask_price nickname|symbol` - Ask price for a stock with symbol or nickname.',
            '`/nickname_add symbol nickname` - Assign a nickname to the stock.',
            '`/nickname_remove symbol|nickname` - Remove a nickname.',
            '`/nickname` - List of defined nicknames.',
            '`/watchlist_add symbol|nickname` - Add an item to watchlist.',
            '`/watchlist_remove symbol|nickname` - Remove an item to watchlist.',
        ])
        reply_markup = telegram.ReplyKeyboardRemove(remove_keyboard=True)
        bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode=telegram.ParseMode.MARKDOWN,reply_markup=reply_markup)

    def setup_handler(self):
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.help_message_handler))
        self.dispatcher.add_handler(CommandHandler(
            'ask_price',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.ask_price(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'nickname_add',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.nickname_add(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'nickname_remove',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.nickname_remove(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'nickname',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.nickname_list(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'watchlist_add',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.watchlist_add(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'watchlist_remove',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.watchlist_remove(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CallbackQueryHandler(callback=self.callback_query_response))

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
                if '/price-movement-percentage' in msg_text:
                    if '/list' in msg_text:
                        message_type = 'notification_manage_price_movement_percentage_list'
                    elif 'view' in msg_text:
                        message_type = 'notification_manage_price_movement_percentage_view'
                    elif 'add' in msg_text:
                        message_type = 'notification_manage_price_movement_percentage_add'
                    elif 'update' in msg_text:
                        message_type = 'notification_manage_price_movement_percentage_update'
                    elif 'remove' in msg_text:
                        message_type = 'notification_manage_price_movement_percentage_remove'
                    else:
                        message_type = None
                elif '/sl' in msg_text:
                    if '/list' in msg_text:
                        message_type = 'notification_manage_sl_list'
                    elif '/view' in msg_text:
                        message_type = 'notification_manage_sl_view'
                    elif '/add' in msg_text:
                        message_type = 'notification_manage_sl_add'
                    elif '/update' in msg_text:
                        message_type = 'notification_manage_sl_update'
                    elif '/remove' in msg_text:
                        message_type = 'notification_manage_sl_remove'
                    else:
                        message_type = None
                elif '/tp' in msg_text:
                    if '/list' in msg_text:
                        message_type = 'notification_manage_tp_list'
                    elif '/view' in msg_text:
                        message_type = 'notification_manage_tp_view'
                    elif '/add' in msg_text:
                        message_type = 'notification_manage_tp_add'
                    elif '/update' in msg_text:
                        message_type = 'notification_manage_tp_update'
                    elif '/remove' in msg_text:
                        message_type = 'notification_manage_tp_remove'
                    else:
                        message_type = None
                else:
                    message_type = None
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

    async def ask_price(self, bot, update, args):
        user_id = update.message.from_user.id
        query_token = ' '.join(args)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        if len(query_token) == 0:
            query = self.check_watchlist(user_id)
        else:
            query = query_token.split(',')
            query = [x.strip() for x in query]
        symbol = [self.check_nickname(user_id, x) for x in query]
        symbol_dict = {x: y for x, y in zip(symbol, query)}
        quotes = await self.scrapper.report_quote(symbol)
        response = '\n'.join(['%s: %s' % (symbol_dict[list(x.keys())[0]], list(x.values())[0]) for x in quotes])
        is_increase = response.find('+') > 0
        is_decrease = response.find('-') > 0
        if is_increase:
            response = '📈 ' + response
        elif is_decrease:
            response = '📉 ' + response
        bot.send_message(chat_id=update.message.chat_id, text=response)

    @staticmethod
    def market_classification(symbol, showIcon):
        marketIcon = ''
        if str(symbol).isdigit():
            market = 'hk'
            marketIcon = '🇭🇰'
        elif not str(symbol).isdigit() and '/' not in str(symbol):
            market = 'us'
            marketIcon = '🇺🇸'
        elif not str(symbol).isdigit() and '/' in str(symbol):
            market = 'forex'
        else:
            market = 'unknonwn'
        if (showIcon):
            return market + ' ' + marketIcon
        else:
            return market

    async def nickname_add(self, bot, update, args):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        symbol, nickname = args
        market = self.market_classification(symbol)
        users = User.objects(telegramUid=user_id)
        Stock(symbol=symbol, nickname=nickname, createdBy=users[0].id, market=market).save()
        marketIcon = self.market_classification(symbol, True)
        response = 'New entry added:\nSymbol: %s, NickName: %s, Market: %s' % (symbol, nickname, marketIcon)
        bot.send_message(chat_id=update.message.chat_id, text=response)

    async def nickname_remove(self, bot, update, args):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        query_token = ''.join(args)
        users = User.objects(telegramUid=user_id)
        if len(query_token) == 0:
            custom_keyboard = []
            stocks = Stock.objects(createdBy=users[0].id)
            for stock in stocks:
                custom_keyboard.append([telegram.KeyboardButton('/nickname_remove '+stock.nickname)])
            reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Please select which nickname to remove.',
                reply_markup=reply_markup,
                one_time_keyboard=True
            )
        else:
            Stock.objects(Q(createdBy=users[0].id) & (Q(symbol=query_token) | Q(nickname=query_token))).delete()
            response = 'Entry removed: %s' % query_token
            bot.send_message(chat_id=update.message.chat_id, text=response)

    async def nickname_list(self, bot, update, args):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        users = User.objects(telegramUid=user_id)
        button_list = []
        stocks = Stock.objects(createdBy=users[0].id)
        for stock in stocks:
            button_list.append([telegram.InlineKeyboardButton(text=stock.nickname + ' - ' + stock.symbol, callback_data='/nickname_list '+stock.nickname)])
        reply_markup = telegram.InlineKeyboardMarkup(button_list)
        response = 'You have _%d_ nicknames' % len(stocks)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response,
            reply_markup=reply_markup,
            parse_mode=telegram.ParseMode.MARKDOWN
        )

    def callback_query_response(self, bot, update):
        bot.answerCallbackQuery(callback_query_id=update.callback_query.id, text=update.callback_query.data)


    async def watchlist_add(self, bot, update, args):
        user_id = update.message.from_user.id
        query_token = ' '.join(args)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        new_symbol_list = query_token.split(',')
        new_symbol_list = [x.strip() for x in new_symbol_list]
        old_symbol_list = self.check_watchlist(user_id)
        symbol_list = list(set(old_symbol_list + new_symbol_list))
        users = User.objects(telegramUid=user_id)
        # Watchlist.objects(createdBy=users[0].id).delete()
        Watchlist.objects(createdBy=users[0].id).update_one(stockSymbols=symbol_list, upsert=True)
        # Watchlist(createdBy=users[0].id, stockSymbols=symbol_list).save()
        response = 'Watchlist added with symbols:\n%s' % ', '.join(new_symbol_list)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def watchlist_remove(self, bot, update, args):
        user_id = update.message.from_user.id
        query_token = ' '.join(args)
        del_symbol_list = query_token.split(',')
        del_symbol_list = [x.strip() for x in del_symbol_list]
        old_symbol_list = self.check_watchlist(user_id)
        symbol_list = [x for x in old_symbol_list if x not in del_symbol_list]
        users = User.objects(telegramUid=user_id)
        Watchlist.objects(createdBy=users[0].id).delete()
        Watchlist(createdBy=users[0].id, stockSymbols=symbol_list).save()
        response = 'Watchlist removed the symbols:\n%s' % ', '.join(del_symbol_list)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def position_add(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/position/add ', '')
        symbol, buyprice, buyunit = query_token.split(' ')
        symbol = symbol.strip()
        buyprice = float(buyprice.strip())
        buyunit = float(buyunit.strip())
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

    async def position_remove(self, message):
        msg_text = message['text']
        user_id = message['from']['id']
        query_token = msg_text.replace('/position/remove ', '')
        query = query_token.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        Position.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id)).delete()
        response = 'Position removed for %s' % stock[0].symbol
        await self.send_message(response, user_id)

    async def notification_manage_list(self, message, method):
        user_id = message['from']['id']
        users = User.objects(telegramUid=user_id)
        notification = NotificationSetting.objects(Q(createdBy=users[0].id) & Q(type=method) & Q(enabled=True))
        notification = ['Symbol: %s, Nickname: %s, Threshold: %s, Type: %s' % (
            x.stock.symbol, x.stock.nickname, x.threshold, x.type) for x in notification]
        response = '\n'.join(notification)
        await self.send_message(response, user_id)

    async def notification_manage_price_movement_percentage_list(self, message):
        await self.notification_manage_list(message, 'priceChange')

    async def notification_manage_sl_list(self, message):
        await self.notification_manage_list(message, 'sl')

    async def notification_manage_tp_list(self, message):
        await self.notification_manage_list(message, 'tp')

    async def notification_manage_view(self, message, method):
        msg_text = message['text']
        user_id = message['from']['id']
        method_dict = {'priceChange': 'price-movement-percentage', 'sl': 'sl', 'tp': 'tp'}
        replace_text = '/notification/manage/%s/view ' % method_dict[method]
        query_token = msg_text.replace(replace_text, '')
        query = query_token.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        notification = NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id) & Q(
            type=method) & Q(enabled=True))
        response = 'Symbol: %s, Nickname: %s, Threshold: %s, Type: %s' % (
            notification[0].stock.symbol, notification[0].stock.nickname, notification[0].threshold,
            notification[0].type)
        await self.send_message(response, user_id)

    async def notification_manage_price_movement_percentage_view(self, message):
        await self.notification_manage_view(message, 'priceChange')

    async def notification_manage_sl_view(self, message):
        await self.notification_manage_view(message, 'sl')

    async def notification_manage_tp_view(self, message):
        await self.notification_manage_view(message, 'tp')

    async def notification_manage_add(self, message, method):
        msg_text = message['text']
        user_id = message['from']['id']
        method_dict = {'priceChange': 'price-movement-percentage', 'sl': 'sl', 'tp': 'tp'}
        replace_text = '/notification/manage/%s/add ' % method_dict[method]
        query_token = msg_text.replace(replace_text, '')
        query, threshold = query_token.split(' ')
        query = query.strip()
        threshold = threshold.strip()
        if '%' in threshold:
            threshold = float(threshold.replace('%', '')) / 100
        else:
            threshold = float(threshold)
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        NotificationSetting(createdBy=users[0].id, stock=stock[0].id, type=method, threshold=threshold,
                            enabled=True).save()
        response = 'Notification added:\nSymbol: %s, Nickname: %s, Threshold: %s, Type: %s' % (
            stock[0].symbol, stock[0].nickname, threshold, method)
        await self.send_message(response, user_id)

    async def notification_manage_price_movement_percentage_add(self, message):
        await self.notification_manage_add(message, 'priceChange')

    async def notification_manage_sl_add(self, message):
        await self.notification_manage_add(message, 'sl')

    async def notification_manage_tp_add(self, message):
        await self.notification_manage_add(message, 'tp')

    async def notification_manage_remove(self, message, method):
        msg_text = message['text']
        user_id = message['from']['id']
        method_dict = {'priceChange': 'price-movement-percentage', 'sl': 'sl', 'tp': 'tp'}
        replace_text = '/notification/manage/%s/remove ' % method_dict[method]
        query_token = msg_text.replace(replace_text, '')
        query = query_token.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id) & Q(type=method)).update(
            enabled=False)
        response = 'Notification removed for symbol %s of type %s' % (stock[0].symbol, method)
        await self.send_message(response, user_id)

    async def notification_manage_price_movement_percentage_remove(self, message):
        await self.notification_manage_remove(message, 'priceChange')

    async def notification_manage_sl_remove(self, message):
        await self.notification_manage_remove(message, 'sl')

    async def notification_manage_tp_remove(self, message):
        await self.notification_manage_remove(message, 'tp')

    async def notification_switch(self, message, enable):
        user_id = message['from']['id']
        users = User.objects(telegramUid=user_id)
        UserSettings.objects(createdBy=users[0].id).update(notificationEnable=enable)
        response = 'Notification %s' % ('enabled' if enable else 'disabled')
        await self.send_message(response, user_id)

    async def notification_enable(self, message):
        await self.notification_switch(message, True)

    async def notification_disable(self, message):
        await self.notification_switch(message, False)

    def get_notification(self):
        notification = NotificationSetting.objects(enabled=True)
        notification = list(map(lambda x: {'user_id': x.createdBy.telegramUid, 'symbol': x.stock.symbol, 'type': x.type,
                                           'threshold': x.threshold}, notification))
        return notification

    def price_change_notification(self, quote, notification):
        if ',' in quote:
            percentage_change = abs(float(quote.split('(')[-1].split('%', 0)) / 100)
            if percentage_change > notification['threshold']:
                notification_message += {'user_id': notification['user_id'],
                                              'message': 'Price change percentage for %s reached.' %
                                                         notification['symbol']}
                users = User.objects(telegramUid=notification['user_id'])
                stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=notification['symbol']))
                NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id))



    async def loop_check_notification(self):
        while True:
            notification = self.get_notification()
            symbols = [x['symbol'] for x in notification]
            quotes = await self.scrapper.report_quote(symbols)


def main():
    tg_bot = TelegramBot()
    tg_bot.setup_handler()
    tg_bot.updater.start_polling()
    # print(tg_bot.loop.run_until_complete(tg_bot.get_message()))
    # print(tg_bot.loop.run_until_complete(tg_bot.get_unprocessed_message()))
    # print(tg_bot.loop.run_until_complete(tg_bot.send_message('Testing', 189497538)))
    # print(tg_bot.check_watchlist(189497538))
    # asyncio.set_event_loop(tg_bot.loop)
    # print(tg_bot.loop.run_until_complete(
    #     tg_bot.watchlist_remove({'message_id': 29, 'from': {'id': 189497538, 'is_bot': False, 'first_name': 'SCTYS', 'username': 'sctys', 'language_code': 'en-US'}, 'chat': {'id': 189497538, 'first_name': 'SCTYS', 'username': 'sctys', 'type': 'private'}, 'date': 1540632514, 'text': '/watchlist/remove 66, 821'})
    #     ))
    # print(tg_bot.loop.run_until_complete(tg_bot.get_message()))
    # tg_bot.loop.run_until_complete()
    # print(tg_bot.check_watchlist(263664408))
    # asyncio.set_event_loop(tg_bot.loop)
    # print(tg_bot.loop.run_until_complete(tg_bot.notification_disable({'message_id': 29, 'from': {'id': 263664408, 'is_bot': False, 'first_name': 'SCTYS', 'username': 'sctys', 'language_code': 'en-US'}, 'chat': {'id': 263664408, 'first_name': 'SCTYS', 'username': 'sctys', 'type': 'private'}, 'date': 1540632514, 'text': '/notification/disable'})))


if __name__ == '__main__':
    main()



