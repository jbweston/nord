const path = require('path') ;
const HtmlWebpackPlugin = require('html-webpack-plugin') ;

const HtmlWebpackPluginConfig = new HtmlWebpackPlugin({
    template: './web/index.html',
    filename: 'index.html',
    inject: 'body'
})

module.exports = {
    entry: ['babel-polyfill', './web/index.jsx'],
    output: {
        path: path.resolve(__dirname, 'nord', 'web', 'static'),
        filename: 'index_bundle.js',
    },
    plugins: [HtmlWebpackPluginConfig],
    module: {
        loaders: [
            {
                test: /\.(jsx|js)$/,
                exclude: /node_modules/,
                loader: 'babel-loader',
                query: {
                    plugins: ['transform-runtime'],
                    presets: ['es2015', 'react', 'stage-3']
                }
            },
            {
                test: /\.css/,
                use: ['style-loader', 'css-loader']
            }
        ]
    }
} ;
