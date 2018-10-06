const mongoose = require('mongoose');

const Schema = new mongoose.Schema({
    // Ref User.id
    createdBy: { type: Number, index: true },
    stockSymbol: String,
    threshold: Number,
    type: {
        type: String,
        enum: ['sl', 'tp', 'priceChange']
    }
});

module.exports = mongoose.model('NotificationSetting', Schema);