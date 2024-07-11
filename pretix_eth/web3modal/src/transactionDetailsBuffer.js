import localForage from "localforage";
import {
  getCookie,
  getTransactionDetailsURL,
  showError,
  showSuccessMessage
} from './interface.js';
import { runPeriodicCheck } from './periodic_check.js';
import { queuePromise } from "./queuePromise";

// Design note: when the real 3cities SDK is ready, this entire subsystem of tracking transaction details pending server submission can be managed inside the SDK. The client API can be quite thin, maybe just (1) provide a primary key for each transaction details (orderId, accountId, function to generate an accountId given 3cities txn details, etc), and (2) provide a function that accepts a pending (primaryKey, txDetails) and returns a Promise that resolves iff the pending details were successfully submitted to the server; this allows the client to own any submission logic, while making it easy to mark tx details as submitted inside the 3cities SDK.

// parseOrderIdFromTransactionDetailsURL takes in a pretix plugin
// transaction details URL like ".../Test/w9vgc/order/:orderId:/..." and
// returns the order ID. Behavior is undefined if the passed URL doesn't
// conform to this shape.
function parseOrderIdFromTransactionDetailsURL(url) {
  const match = url.match(/\/order\/([^\/]+)\//);
  return match ? match[1] : undefined;
}

const storageKey = "pretix_eth_transaction_details_buffer";

async function getAllPendingTransactionDetailsSkipQueue() {
  const r = await localForage.getItem(storageKey);
  return r === null ? {} : r;
}

// addPendingTransactionDetails schedules pending onchain transaction
// details to be submitted to the server. The passed details must be for
// the orderId implied by this page's URL.
export async function addPendingTransactionDetails({ transactionDetailsUrlSearchParams }) { // TODO real return type that shows if it already existed, was overwritten, etc.
  return queuePromise(storageKey, async () => {
    const p = await getAllPendingTransactionDetailsSkipQueue(); // WARNING here we must use getPendingTransactionDetailsSkipQueue to skip the promise queue, or else we'll deadlock the promise queue as this promise depends on the subsequentedly queued getMostRecentlyUsed promise to settle. Note that skipping the queue here is correct behavior as queuePromise guarantees that any potentially conflicting changes have already settled before this promise runs
    const orderId = parseOrderIdFromTransactionDetailsURL(getTransactionDetailsURL());
    p[orderId] = transactionDetailsUrlSearchParams;
    await localForage.setItem(storageKey, p);
  });
}

async function markPendingTransactionDetailsAsSuccessfullySubmitted({ orderId }) { // TODO real return type that shows if details for this orderId existed or not
  return queuePromise(storageKey, async () => {
    const p = await getAllPendingTransactionDetailsSkipQueue(); // WARNING here we must use getPendingTransactionDetailsSkipQueue to skip the promise queue, or else we'll deadlock the promise queue as this promise depends on the subsequentedly queued getMostRecentlyUsed promise to settle. Note that skipping the queue here is correct behavior as queuePromise guarantees that any potentially conflicting changes have already settled before this promise runs
    delete p[orderId];
    await localForage.setItem(storageKey, p);
  });
}

async function getAllPendingTransactionDetails() {
  return queuePromise(storageKey, async () => {
    return getAllPendingTransactionDetailsSkipQueue();
  });
}

export async function monitorAndSubmitPendingTransactionDetails(attempt = 1) {
  let nextAttempt = 1; // value of `attempt` to pass to next invocatin of this function. Default to 1 "attempt" as this causes the exponential backoff algorithm to be disabled by default, which is what we want, since we only want to exponentially backoff on a network error.

  const allPendingTransactionDetails = Object.entries(await getAllPendingTransactionDetails()); // ie. type is `allPendingTransactionDetails: [orderId, txDetails][]`
  if (allPendingTransactionDetails.length > 0) {
    const url = getTransactionDetailsURL();
    const orderIdForThisPage = parseOrderIdFromTransactionDetailsURL(url);
    const orderIdAndTxDetails = allPendingTransactionDetails.find(pair => { // WARNING, here, while there may be multiple pending tx details, we are only able to submit at most one tx details because the transaction details POST url is unique to a particular order Id
      const orderId = pair[0]; // ie. pair type is [orderId, txDetails]
      return orderId === orderIdForThisPage;
    });
    if (orderIdAndTxDetails) {
      const [orderIdToSubmit, txDetailsToSubmit] = orderIdAndTxDetails;
      try {
        const csrf_cookie = getCookie('pretix_csrftoken') || getCookie('__Host-pretix_csrftoken'); // in devserver builds, pretix provides pretix_csrftoken without the __Host- pretix. WARNING here we must use the latest csrf_cookie, it wasn't included in the saved tx details because it might have changed if the user's session changed between the time when tx details were saved and time now when submission occurs
        const params = {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            'X-CSRFToken': csrf_cookie,
          },
          method: 'POST',
          mode: 'same-origin',
          body: new URLSearchParams({
            ...txDetailsToSubmit,
            csrfmiddlewaretoken: csrf_cookie,
          }),
        };
        const response = await fetch(url, params);
        if (response.ok) {
          showError(' ', false); // clear any error from previous attempts --> the non-empty whitespace string here is essential to avoid a default error message
          showSuccessMessage(txDetailsToSubmit);
          await markPendingTransactionDetailsAsSuccessfullySubmitted({ orderId: orderIdToSubmit }); // these txDetails have been successfully submitted to the server, and now we must un-schedule them to prevent any future attempted submission
          await runPeriodicCheck(); // begin monitoring for the payment being confirmed by the server
        } else {
          throw new Error('transaction details submission fetch response not OK');
        }
      } catch (error) {
        (() => { // pending transaction details were detected for this page's order ID, so paying again would result in a duplicate payment, and submitting these pending details to the server had an error, so we must hide the pay button to prevent duplicate payments. NB the pay button is hidden by another mechanism if pending details server submission is successful, so here we only worry about hiding the button iff pending tx details for this order ID exist but submission failed
          const payBtn = document.getElementById("btn-pay");
          if (payBtn) payBtn.style.display = 'none';
        })();
        showError(`🚨🚨🚨 Do not close this window yet! There was an error processing your payment. We will re-try shortly. If this error does not go away, please contact support. Save these details: Your payment was sent in transaction ${txDetailsToSubmit.transactionHash} on ${txDetailsToSubmit.chainName} (chain ID ${txDetailsToSubmit.chainId}). Receipt link ${txDetailsToSubmit.receiptUrl}.`, false);
        nextAttempt = attempt + 1; // submission POST failed, so we will retry with exponential backoff, where exponential backoff is enabled by incrementing current attempt count
      }
    }
  }
  const maxBackoff = 15_000; // maximum backoff time in milliseconds (15 seconds)
  const backoff = Math.min(maxBackoff, Math.pow(2, attempt) * 250); // exponential backoff formula
  setTimeout(() => monitorAndSubmitPendingTransactionDetails(nextAttempt), backoff); // unconditionally continue monitoring as new tx detaisl for submission may become available or existing pending details may have failed submission
}

(() => { // begin monitoring for pending transaction details when page loads
  monitorAndSubmitPendingTransactionDetails();
})();
