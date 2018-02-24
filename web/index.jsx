import 'bulma/css/bulma.css'

import React from 'react' ;
import ReactDOM from 'react-dom' ;

import Nord from './components/Nord.jsx' ;

const root = document.getElementById('root') ;
if (root == null) {
    throw new Error("No root element") ;
} else {
    ReactDOM.render(<Nord />, root) ;
}
