const mongoose = require('mongoose');

const Schema = new mongoose.Schema({
    // Ref User.id
    createdBy: { type: Number, index: true },
    notificationEnable: Boolean
});

module.exports = mongoose.model('UserSetting', Schema);