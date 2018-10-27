from db import *

for position in Position.objects():
    print(position.unitPrice)
    print(position.createdBy.name)
    print(position.stock.symbol)