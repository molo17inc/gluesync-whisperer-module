import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

console.log('Main.tsx loaded');
const root = ReactDOM.createRoot(document.getElementById('root')!);
console.log('Root created');
root.render(
  
    <App />
  
);
console.log('App rendered');
