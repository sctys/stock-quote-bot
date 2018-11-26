import aiohttp
import asyncio
import os
import logging
import json
import threading
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
            '`/position_add symbol|nickname buyprice buyunit` - Add an item to position.',
            '`/position_remove symbol|nickname` - Remove an item from positions.',
            '`/positions` - List of positions.',
            '`/position symbol|nickname` - View a position.',
            '`/notifications sl|tp|change` - List of notification.',
            '`/notification_add sl|tp|change` - Add a type of notification.',
            '`/notification_remove sl|tp|change` - Remove a type of notification.',
            '`/notification sl|tp|change` - View a type of notification.',
            '`/notification_enable` - Enable all notifications.',
            '`/notification_disable` - Disable all notifications.',
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
        self.dispatcher.add_handler(CommandHandler(
            'position_add',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.position_add(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'positions',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.position_list(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'position',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.position_view(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'position_remove',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.position_remove(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'notifications',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.notification_manage_list(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'notification_add',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.notification_manage_add(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'notification_remove',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.notification_manage_remove(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'notification_enable',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.notification_enable(bot, update, args)),
            pass_args=True))
        self.dispatcher.add_handler(CommandHandler(
            'notification_disable',
            callback=lambda bot, update, args: self.loop.run_until_complete(self.notification_disable(bot, update, args)),
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
        is_increase = float(response.split(',')[-1].split('(')[0]) > 0
        is_decrease = response.find('-') > 0
        if is_increase:
            response = '📈 ' + response
        elif is_decrease:
            response = '📉 ' + response
        bot.send_message(chat_id=update.message.chat_id, text=response)

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

    @staticmethod
    def market_icon(symbol):
        market_icon = ''
        if str(symbol).isdigit():
            market_icon = '🇭🇰'
        elif not str(symbol).isdigit() and '/' not in str(symbol):
            market_icon = '🇺🇸'
        elif not str(symbol).isdigit() and '/' in str(symbol):
            market_icon = ''
        return market_icon

    @staticmethod
    def get_method_name(method):
        if (method == 'change'):
            return 'priceChange'
        else:
            return method

    async def nickname_add(self, bot, update, args):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        symbol, nickname = args
        market = self.market_classification(symbol)
        users = User.objects(telegramUid=user_id)
        Stock(symbol=symbol, nickname=nickname, createdBy=users[0].id, market=market).save()
        market_icon = self.market_icon(symbol)
        response = '✅ New entry added:\nSymbol: %s, NickName: %s, Market: %s%s' % (symbol, nickname, market, market_icon)
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
            response = '❎ Entry removed: %s' % query_token
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
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
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

    async def position_add(self, bot, update, args):
        user_id = update.message.from_user.id
        query_token = ' '.join(args)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        symbol, buyprice, buyunit = query_token.split(' ')
        symbol = symbol.strip()
        buyprice = float(buyprice.strip())
        buyunit = float(buyunit.strip())
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=symbol))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=symbol))
        Position(createdBy=users[0].id, stock=stock[0].id, unitPrice=buyprice, quantity=buyunit).save()
        response = '✅ Position added for %s, unit price = %s, quantity = %s' % (stock[0].symbol, buyprice, buyunit)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def position_list(self, bot, update, args):
        user_id = update.message.from_user.id
        users = User.objects(telegramUid=user_id)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        position = Position.objects(createdBy=users[0].id)
        position = ['Symbol: %s, Nickname: %s, unit price: %s, quantity: %s' % (
            x.stock.symbol, x.stock.nickname, x.unitPrice, x.quantity) for x in position]
        response = '\n'.join(position)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def position_view(self, bot, update, args):
        user_id = update.message.from_user.id
        users = User.objects(telegramUid=user_id)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        query_token = ' '.join(args)
        query = query_token.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        position = Position.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id))
        position = position[0]
        stock = stock[0]
        old_price = position.unitPrice
        quantity = position.quantity
        new_price = await self.scrapper.report_quote([stock.symbol])
        new_price = new_price[0][stock.symbol].split(',')[0]
        profit = (float(new_price) - float(old_price)) * quantity
        percent_profit = str((float(new_price) / float(old_price) - 1) * 100) + '%'
        if profit > 0:
            response = '😆 Profit = %s, Percent profit = %s' % (profit, percent_profit)
        else:
            response = '😭 Loss = %s, Percent loss = %s' % (profit, percent_profit)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def position_remove(self, bot, update, args):
        user_id = update.message.from_user.id
        users = User.objects(telegramUid=user_id)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        query_token = ' '.join(args)
        query = query_token.strip()
        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        Position.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id)).delete()
        response = '❎ Position removed for %s' % stock[0].symbol
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def notification_manage_list(self, bot, update, args):
        user_id = update.message.from_user.id
        users = User.objects(telegramUid=user_id)
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        notification = NotificationSetting.objects(Q(createdBy=users[0].id) & Q(enabled=True))
        if len(notification) == 0:
            response = 'You have no notification for %s' % method
        else:
            notification = ['🔈 Symbol: %s, Nickname: %s, \n       Threshold: %s, Type: %s' % (
            x.stock.symbol, x.stock.nickname, x.threshold, x.type) for x in notification]
            response = '\n'.join(notification)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

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

    async def notification_manage_add(self, bot, update, args):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        method = self.get_method_name(args[0])
        query = args[1]
        threshold = args[2]

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
        response = '🔈 Notification added:\nSymbol: %s, Nickname: %s, Threshold: %s, Type: %s' % (
            stock[0].symbol, stock[0].nickname, threshold, method)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def notification_manage_price_movement_percentage_add(self, message):
        await self.notification_manage_add(message, 'priceChange')

    async def notification_manage_sl_add(self, message):
        await self.notification_manage_add(message, 'sl')

    async def notification_manage_tp_add(self, message):
        await self.notification_manage_add(message, 'tp')

    async def notification_manage_remove(self, bot, update, args):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        method = self.get_method_name(args[0])
        query = args[1]

        users = User.objects(telegramUid=user_id)
        stock = Stock.objects(Q(createdBy=users[0].id) & Q(nickname=query))
        if len(stock) == 0:
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=query))
        NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id) & Q(type=method)).update(
            enabled=False)
        response = '🔇 Notification removed for symbol %s of type %s' % (stock[0].symbol, method)
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def notification_manage_price_movement_percentage_remove(self, message):
        await self.notification_manage_remove(message, 'priceChange')

    async def notification_manage_sl_remove(self, message):
        await self.notification_manage_remove(message, 'sl')

    async def notification_manage_tp_remove(self, message):
        await self.notification_manage_remove(message, 'tp')

    async def notification_switch(self, bot, update, enable):
        user_id = update.message.from_user.id
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        users = User.objects(telegramUid=user_id)
        UserSettings.objects(createdBy=users[0].id).update(notificationEnable=enable)
        if enable:
            response = '🔈 Notification enabled'
        else:
            response = '🔇 Notification disabled'
        bot.send_message(
            chat_id=update.message.chat.id,
            text=response
        )

    async def notification_enable(self, bot, update, args):
        await self.notification_switch(bot, update, True)

    async def notification_disable(self, bot, update, args):
        await self.notification_switch(bot, update, False)

    def get_notification(self):
        notification = NotificationSetting.objects(enabled=True)
        notification = list(map(lambda x: {'user_id': x.createdBy.telegramUid, 'symbol': x.stock.symbol, 'type': x.type,
                                           'threshold': x.threshold}, notification))
        user_enabled = [x.createdBy.telegramUid for x in UserSettings.objects(notificationEnable=True)]
        notification = [x for x in notification if x['user_id'] in user_enabled]
        return notification

    async def price_change_notification(self, notification):
        if ',' in notification['quote']:
            percentage_change = abs(float(notification['quote'].split('(')[-1].split('%')[0]) / 100)
            if percentage_change > notification['threshold']:
                users = User.objects(telegramUid=notification['user_id'])
                stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=notification['symbol']))
                NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id) & Q(
                    type='priceChange')).update(enabled=False)
                await self.send_message(user_id=notification['user_id'],
                                        content='Price change percentage for %s reached.' % notification['symbol'])

    async def sl_notification(self, notification):
        price = float(notification['quote'].split(',')[0])
        if price < notification['threshold']:
            users = User.objects(telegramUid=notification['user_id'])
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=notification['symbol']))
            [NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=x.id) & Q(
                type='sl')).update(enabled=False) for x in stock]
            await self.send_message(user_id=notification['user_id'],
                                    content='SL for %s reached.' % notification['symbol'])

    async def tp_notification(self, notification):
        price = float(notification['quote'].split(',')[0])
        if price > notification['threshold']:
            users = User.objects(telegramUid=notification['user_id'])
            stock = Stock.objects(Q(createdBy=users[0].id) & Q(symbol=notification['symbol']))
            NotificationSetting.objects(Q(createdBy=users[0].id) & Q(stock=stock[0].id) & Q(type='tp')).update(
                enabled=False)
            await self.send_message(user_id=notification['user_id'],
                                    content='TP for %s reached.' % notification['symbol'])

    async def loop_check_notification(self):
        while True:
            notification = self.get_notification()
            symbols = [x['symbol'] for x in notification]
            quotes = await self.scrapper.report_quote(symbols)
            notification = [{**x, **{'quote': [y for y in quotes if x['symbol'] in y][0][x['symbol']]}}
                            for x in notification]
            price_change_notification = [x for x in notification if x['type'] == 'priceChange']
            sl_notification = [x for x in notification if x['type'] == 'sl']
            tp_notification = [x for x in notification if x['type'] == 'tp']
            [await self.price_change_notification(x) for x in price_change_notification] + [
                await self.sl_notification(x) for x in sl_notification] + [
                await self.tp_notification(x) for x in tp_notification]
            await asyncio.sleep(60)

    def thread_check_notification(self):
        asyncio.set_event_loop(self.loop)
        thread = threading.Thread(target=lambda: self.loop.run_until_complete(self.loop_check_notification()),
                                  daemon=True)
        thread.start()


def main():
    tg_bot = TelegramBot()
    tg_bot.setup_handler()
    tg_bot.thread_check_notification()
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
    # print(tg_bot.loop.run_until_complete(tg_bot.notification_enable({'message_id': 29, 'from': {'id': 263664408, 'is_bot': False, 'first_name': 'SCTYS', 'username': 'sctys', 'language_code': 'en-US'}, 'chat': {'id': 263664408, 'first_name': 'SCTYS', 'username': 'sctys', 'type': 'private'}, 'date': 1540632514, 'text': '/notification/enable'})))


if __name__ == '__main__':
    main()



