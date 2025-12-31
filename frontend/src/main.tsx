import React from "react";
import { BrowserRouter } from "react-router-dom";
import ReactDOM from "react-dom/client";
import App from "./App";
import { getRouterBaseName } from "./utils/basePath";

console.log("Main.tsx loaded");
const root = ReactDOM.createRoot(document.getElementById("root")!);
console.log("Root created");
const basename = getRouterBaseName();
root.render(
  <BrowserRouter basename={basename}>
    <App />
  </BrowserRouter>
);
console.log("App rendered");
