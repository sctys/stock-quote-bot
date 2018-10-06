var mongoose = require('mongoose');

let User = require('./models/user');
let Position = require('./models/position');
let Stock = require('./models/stock');
let Watchlist = require('./models/watchlist');
let UserSetting = require('./models/userSetting');
let NotificationSetting = require('./models/notificationSetting');

function create() {
    const aUser = {
        name: 'Shark',
        id: 11111111111
    };
    User.create(aUser, (err, res) => handler);

    Stock.create({
        symbol: 'GOOG',
        nickname: 'Google',
        createdBy: aUser.id,
        market: 'us'
    }, (err, res) => handler);

    Watchlist.create({
        createdBy: aUser.id,
        stockSymbols: ['GOOG']
    }, (err, res) => handler);

    Position.create({
        nickname: 'My first stock',
        stockSymbol: 'GOOG',
        createdBy: aUser.id,
        unitPrice: 1200,
        quantity: 10
    }, (err, res) => handler);

    UserSetting.create({
        createdBy: aUser.id,
        notificationEnable: true
    }, (err, res) => handler);

    NotificationSetting.create({
        createdBy: aUser.id,
        stockSymbol: 'GOOG',
        threshold: 1100,
        type: 'sl'
    }, (err, res) => handler);

}

function handler(err, res) {
    if (err) {
        return console.error(err);
    }
    console.log('Created ', res);
}

module.exports.create = create;