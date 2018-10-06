const mongoose = require('mongoose');

const Schema = new mongoose.Schema({
    id: {
        type: Number,
        unique: true
    },
    name: String
}, { id: false });

module.exports = mongoose.model('User', Schema);