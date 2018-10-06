const mongoose = require('mongoose');

const Schema = new mongoose.Schema({
    nickname: { type: String, index: true },
    // Ref User.id
    createdBy: { type: Number, index: true },
    stockSymbol: String,
    unitPrice: Number,
    quantity: Number
});

module.exports = mongoose.model('Position', Schema);