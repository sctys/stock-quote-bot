from db import *

aUser = User(_id=263664408, name="SiMon")
aUser.save()

for user in User.objects(_id=263664408):
    aStock = Stock(
        createdBy=user._id,
        symbol="GOOG",
        nickname="Google",
        market="us",
    )
    aStock.save()

    aPosition = Position(
            createdBy=user._id,
            stock=aStock,
            unitPrice=1200,
            quantity=10)
    aPosition.save()

    aUserSettings = UserSettings(
        createdBy=user._id,
        notificationEnable=True
    )
    aUserSettings.save()

    aWatchlist = Watchlist(
        createdBy=user._id,
        stockSymbols=['GOOG']
    )
    aWatchlist.save()

    aNotificationSetting = NotificationSetting(
        createdBy=user._id,
        stockSymbol="GOOG",
        threshold=1100,
        type="sl"
    )
    aNotificationSetting.save()