import os
from mongoengine import *

connect(host=os.environ['DB_CONN'])

class User(Document):
    telegramUid = IntField(unique=True)
    name = StringField()
    meta = {
        'collection': 'users'
    }

class UserSettings(Document):
    createdBy = ReferenceField(User)
    notificationEnable = BooleanField()
    v = IntField(db_field='__v')
    meta = {
        'collection': 'usersettings'
    }

class Watchlist(Document):
    createdBy = ReferenceField(User)
    stockSymbols = ListField(StringField())
    v = IntField(db_field='__v')
    meta = {
        'collection': 'watchlists',
        'indexes': [
            'stockSymbols'
        ]
    }

class Stock(Document):
    createdBy = ReferenceField(User)
    symbol = StringField()
    nickname = StringField()
    market = StringField()
    v = IntField(db_field='__v')
    meta = {
        'collection': 'stocks',
        'indexes': [
            'symbol',
            'nickname',
            'market'
        ]
    }

class Position(Document):
    createdBy = ReferenceField(User)
    stock = ReferenceField(Stock)
    unitPrice = DecimalField()
    quantity = IntField()
    v = IntField(db_field='__v')
    meta = {
        'collection': 'positions',
        'indexes': []
    }

class NotificationSetting(Document):
    createdBy = ReferenceField(User)
    stockSymbol = StringField()
    threshold = DecimalField()
    type = StringField(choices=('sl', 'tp', 'priceChange'))
    v = IntField(db_field='__v')
    meta = {
        'collection': 'notificationsettings',
        'indexes': [
            'stockSymbol'
        ]
    }
