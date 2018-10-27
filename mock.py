from db import *

# aUser = User(telegramUid=263664408, name="SiMon")
#aUser.save()

for user in User.objects(telegramUid=263664408):
    aStock = Stock(
        createdBy=user.id,
        symbol="GOOG",
        nickname="Google",
        market="us",
    )
    aStock.save()

    aPosition = Position(
            createdBy=user.id,
            stock=aStock,
            unitPrice=1200,
            quantity=10)
    aPosition.save()

    aUserSettings = UserSettings(
        createdBy=user.id,
        notificationEnable=True
    )
    aUserSettings.save()

    aWatchlist = Watchlist(
        createdBy=user.id,
        stockSymbols=['GOOG']
    )
    aWatchlist.save()

    aNotificationSetting = NotificationSetting(
        createdBy=user.id,
        stockSymbol="GOOG",
        threshold=1100,
        type="sl"
    )
    aNotificationSetting.save()