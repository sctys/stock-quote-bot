const mongoose = require('mongoose');

const Schema = new mongoose.Schema({
    symbol: { type: String, index: true },
    nickname: { type: String, index: true },
    // Ref User.id
    createdBy: { type: Number, index: true },
    market: String
});

module.exports = mongoose.model('Stock', Schema);