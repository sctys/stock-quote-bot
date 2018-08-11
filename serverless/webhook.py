from pprint import pprint
import os
import requests

bot_token = os.environ['TELEGRAM_TOKEN']
test_url = os.environ['NGROK_HOST'] + "/{}".format(bot_token)

def get_url(method):
    return "https://api.telegram.org/bot{}/{}".format(bot_token,method)

r = requests.get(get_url("setWebhook"), data={"url": test_url})
r = requests.get(get_url("getWebhookInfo"))
pprint(r.status_code)
pprint(r.json())