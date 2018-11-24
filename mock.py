from db import *

# aUser = User(telegramUid=263664408, name="SiMon")
# aUser.save()

# aUser = User(telegramUid=189497538, name="MayMay")
# aUser.save()

for user in User.objects(telegramUid=189497538):
#     aStock = Stock(
#         createdBy=user.id,
#         symbol="GOOG",
#         nickname="Google",
#         market="us",
#     )
#     aStock.save()

#     aPosition = Position(
#             createdBy=user.id,
#             stock=aStock,
#             unitPrice=1200,
#             quantity=10)
#     aPosition.save()

    aUserSettings = UserSettings(
        createdBy=user.id,
        notificationEnable=True
    )
    aUserSettings.save()

#     aWatchlist = Watchlist(
#         createdBy=user.id,
#         stockSymbols=['GOOG']
#     )
#     aWatchlist.save()

#     aNotificationSetting = NotificationSetting(
#         createdBy=user.id,
#         stock=aStock,
#         threshold=1100,
#         type="sl",
#         enabled=True
#     )
#     aNotificationSetting.save()