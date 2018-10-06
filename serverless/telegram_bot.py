import aiohttp
import asyncio
import os
import logging
import json
from logging.handlers import TimedRotatingFileHandler


class TelegramBot(object):

    def __init__(self):
        self.__token = os.environ['TELEGRAM_TOKEN']
        self.endpoint = 'https://api.telegram.org/bot%s' % self.__token
        self.get_message_url = '/getUpdates'
        self.send_message_url = '/sendMessage'
        self.last_update_id = 0
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
        if '/ask' in msg_text:
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

    async def ask_price(self, message):
        msg_text = message['text']




def main():
    tg_bot = TelegramBot()
    print(tg_bot.loop.run_until_complete(tg_bot.send_message('Nice to meet you', 263664408)))


if __name__ == '__main__':
    main()



