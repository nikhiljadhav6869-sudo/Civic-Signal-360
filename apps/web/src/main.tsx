import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import {InstallPage} from './InstallPage';
import './styles.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{location.pathname.replace(/\/$/,'')==='/install'?<InstallPage/>:<App/>}</React.StrictMode>);
if('serviceWorker' in navigator&&location.protocol!=='file:')window.addEventListener('load',()=>{void navigator.serviceWorker.register('/sw.js').catch(()=>{});});
