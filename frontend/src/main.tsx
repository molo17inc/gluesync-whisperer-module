import React from 'react'
import { BrowserRouter } from 'react-router-dom'
import ReactDOM from 'react-dom/client'
import App from './App'

console.log('Main.tsx loaded');
const root = ReactDOM.createRoot(document.getElementById('root')!);
console.log('Root created');
root.render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
);
console.log('App rendered');
