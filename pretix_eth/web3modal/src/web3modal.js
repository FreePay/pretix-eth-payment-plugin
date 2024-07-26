"use strict";

// TODO rename this file to something-not-web3modal

import { makePayment } from './core.js';

async function init() {
    document.title = 'Pretix Payment'; // some wallets read the page title and presents it to the user in the wallet - the pretix generated one looks confusing, so we override it
    document.getElementById('spinner').style.display = 'none';
    const payButton = document.getElementById('btn-pay');
    if (payButton) payButton.addEventListener('click', makePayment);
    else console.error('No pay button found');
}

init();
