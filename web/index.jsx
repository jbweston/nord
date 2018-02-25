import React from 'react' ;
import ReactDOM from 'react-dom' ;

import Nord from './Nord.jsx' ;

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById('root') ;
  if (root == null) {
      throw new Error("No root element") ;
  } else {
      ReactDOM.render(<Nord />, root) ;
  }
}) ;
