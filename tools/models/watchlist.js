const mongoose = require('mongoose');

const Schema = new mongoose.Schema({
    createdBy: { type: Number, index: true },
    // List of stocks symbol
    stockSymbols: [String]
});

module.exports = mongoose.model('Watchlist', Schema);