const merge = require('webpack-merge');
const common = require('./webpack.config.js');

module.exports = merge(common, {

    devtool: 'eval-source-map',

    devServer: {
        hot: true,
        inline: true,
        proxy: {
            '/api': {
                target: 'http://localhost:5000'
            }
        },
        historyApiFallback: true,
        port: 8881,
        publicPath: '/',
        host: '0.0.0.0',
        overlay: {
            warnings: true,
            errors: true
        },
        watchContentBase: true,
        watchOptions: {
            poll: true
        }
    }
})
