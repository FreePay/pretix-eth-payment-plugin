"use strict";

const GlobalPretixEthState = {
    paymentDetails: null,
    // payment flow flags
    transactionHashSubmitted: false,
    lastOrderStatus: '',
    // interface and data-bearing tags
    elements: {
        divError: document.getElementById("message-error"),
        divSuccess: document.getElementById("success"),
        divTransactionHash: document.getElementById("pretix-eth-transaction-hash"),
        aOrderDetailURL: document.getElementById("pretix-order-detail-url"),
        buttonPay: document.getElementById("btn-pay"),
        submittedTransactionHash: document.getElementById("pretix-eth-submitted-transaction-hash"),
    },
    selectors: {
        paymentSteps: document.querySelectorAll(".pretix-eth-payment-steps")
    },
}

function getTransactionDetailsURL() {
    return GlobalPretixEthState.elements.buttonPay.getAttribute("data-transaction-details-url");
}

async function getPaymentTransactionData(refresh = false) {
    if (!refresh && GlobalPretixEthState.paymentDetails !== null) {
        return GlobalPretixEthState.paymentDetails
    }

    const response = await fetch(getTransactionDetailsURL());

    if (response.status >= 400) { // TODO should this be `if response.status is not 2xx`?
        throw "Failed to fetch order details. If this problem persists, please contact the organizer directly.";
    }

    return await response.json();
}

function getCookie(name) {
    // Add the = sign
    name = name + '=';

    // Get the decoded cookie
    const decodedCookie = decodeURIComponent(document.cookie);

    // Get all cookies, split on ; sign
    const cookies = decodedCookie.split(';');

    // Loop over the cookies
    for (let i = 0; i < cookies.length; i++) {
        // Define the single cookie, and remove whitespace
        const cookie = cookies[i].trim();

        // If this cookie has the name of what we are searching
        if (cookie.indexOf(name) == 0) {
            // Return everything after the cookies name
            return cookie.substring(name.length, cookie.length);
        }
    }
}

/*
* Success and error handling
*/
function showError(message = '', reset_state = true) {
    if (GlobalPretixEthState.transactionHashSubmitted) {
        // do not display errors or reset state after the transaction hash has been successfully submitted to the BE
        message = "";
        reset_state = false;
    } else {
        if (typeof message === "object") {
            if (message.data && message.data.message) {
                message = message.data.message + ". Please try again."
            } else if (message.message !== undefined) {
                message = message.message + ". Please try again."
            } else if (message.error !== undefined && message.error.message !== undefined) {
                message = message.error.message + ". Please try again.";
            } else {
                message = "";
            }
        }
        if (message === "") {
            message = "There was an error, please try again, or contact support if you have already confirmed a payment in your wallet provider."
        }
    }

    GlobalPretixEthState.elements.divError.innerHTML = message;

    if (reset_state === true) {
        displayOnlyId("pay");
    }
    try {
        GlobalPretixEthState.elements.buttonPay.removeAttribute("disabled");
    } catch (e) {
        return false
    }

    return false
}

function resetErrorMessage() {
    GlobalPretixEthState.elements.divError.innerHTML = '';
}

function displayOnlyId(divId) {
    GlobalPretixEthState.selectors.paymentSteps.forEach(
        function (div) {
            if (div.id === divId) {
                div.style.display = "block";
            } else {
                div.style.display = "none";
            }
        }
    );
}

function showSuccessMessage(paymentDetails) {
    GlobalPretixEthState.transactionHashSubmitted = true;
    GlobalPretixEthState.elements.divTransactionHash.innerHTML = `${paymentDetails.transactionHash} (chain ID ${paymentDetails.chainId})`; // TODO final rendering of payment details. Can we show block explorer link passed from 3c here?
    displayOnlyId();
    GlobalPretixEthState.elements.divSuccess.style.display = "block";
}

export {
    GlobalPretixEthState, displayOnlyId, getCookie, getPaymentTransactionData, getTransactionDetailsURL, resetErrorMessage, showError, showSuccessMessage
};
