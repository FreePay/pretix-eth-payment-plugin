import { getCookie, GlobalPretixEthState } from "./interface.js";

// periodicCheck monitors for an existing unconfirmed payment to become
// confirmed and when it does, reload the page to render with fresh
// confirmation state.
async function periodicCheck() {
    let url = GlobalPretixEthState.elements.aOrderDetailURL.getAttribute("data-order-detail-url");
    const csrf_cookie = getCookie('pretix_csrftoken')

    let response = await fetch(url, {
        headers: {
            'X-CSRF-TOKEN': csrf_cookie,
            'HTTP-X-CSRFTOKEN': csrf_cookie,
        }
    });

    if (response.ok) {
        let data = await response.json()
        if (GlobalPretixEthState.lastOrderStatus === '') {
            GlobalPretixEthState.lastOrderStatus = data.status;
        } else if (GlobalPretixEthState.lastOrderStatus !== data.status) {
            // status has changed to PAID
            if (data.status === 'p') {
                location.reload();
            }
        }
    }
}

async function runPeriodicCheck() {
    while (true) {
        try {
            await periodicCheck();
        } catch (e) { }
        await new Promise(resolve => setTimeout(resolve, 5000));
    }
}

export { runPeriodicCheck };
