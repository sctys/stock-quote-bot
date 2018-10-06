var mongoose = require('mongoose');
const DB_CONN = process.env.DB_CONN;

mongoose.connect(DB_CONN, { useNewUrlParser: true });
mongoose.set('useCreateIndex', true);

var db = mongoose.connection;
db.on('error', console.error.bind(console, 'connection error:'));
db.once('open', function () {
    console.log('connected');
});

// let mock = require('./mock');
// mock.create();
