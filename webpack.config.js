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
            { test: /\.css$/,use: ['style-loader', 'css-loader'] },
            { test: /\.(png|jpg|gif)$/, loader: "file-loader" },
            { test: /\.(woff(2)?|ttf|eot|svg|otf)(\?v=\d+\.\d+\.\d+)?$/, loader: "file-loader" },
            { test: /LICENSE/, loader: 'file-loader', options: { name: '[name]'} },
            {
                test: /\.geo\.json/,
                loader: 'file-loader',
                options: {
                  name: '[name].[ext]'
                }
            },
        ]
    }
} ;
