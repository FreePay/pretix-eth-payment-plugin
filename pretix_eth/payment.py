import logging
import time
from collections import OrderedDict

from json import JSONDecoder, loads, JSONDecodeError

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from pretix.base.models import (
    OrderPayment,
    OrderRefund,
)
from pretix.base.payment import BasePaymentProvider

from pretix_eth.models import SignedMessage
from pretix_eth.network.helpers import get_eth_price_from_external_apis

logger = logging.getLogger(__name__)


class Ethereum(BasePaymentProvider):
    identifier = "ethereum"
    verbose_name = _("Pay on Ethereum")
    public_name = _("Pay on Ethereum")
    test_mode_message = "Paying in Test Mode"

    @property
    def settings_form_fields(self):
        # TODO add 3cities settings eg. 3cities base url (remember, base url's receiver address must coincidentally match configured receiver address in plugin), verifier grpc endpoint. Perhaps have different endpoints for testnet and mainnet and then these can be chosen from at runtime using pretix's test mode flag
        form_fields = OrderedDict(
            list(super().settings_form_fields.items())
            + [
                (
                    "SINGLE_RECEIVER_ADDRESS",
                    forms.CharField(
                        label=_("Payment receiver address."),
                        help_text=_("Caution: Must work on all networks configured.")
                    )
                ),
                # TODO PAYMENT_NOT_RECIEVED_RETRY_TIMEOUT is no longer used. Should it be used again or removed?
                # (
                #     "PAYMENT_NOT_RECIEVED_RETRY_TIMEOUT",
                #     forms.IntegerField(
                #         label=_("Payment retry timeout in seconds"),
                #         help_text=_(
                #             "Customers will be allowed to pay again after their previous payment "
                #             "hasn't arrived for a given time. "
                #             "1800s (30min) is a reasonable starting value"
                #         ),
                #         initial=30 * 60,
                #     )
                # ),
            ]
        )

        return form_fields

    def get_receiving_address(self):
        return self.settings.SINGLE_RECEIVER_ADDRESS

    def is_allowed(self, request, **kwargs):
        is_event_currency_supported = self.event.currency == "USD"  # TODO support EUR payments
        if not is_event_currency_supported:
            logger.error("The Ethereum payment provider only supports USD denominated events.")

        receiving_address = self.get_receiving_address()
        single_receiver_mode_configured = bool(
            receiving_address is not None
            and len(receiving_address) > 0
        )

        if not single_receiver_mode_configured:
            logger.error("Single receiver addresses not configured properly")

        return all(
            (
                is_event_currency_supported,
                single_receiver_mode_configured,
                super().is_allowed(request, **kwargs),
            )
        )

    def payment_form_render(self, request, total, order=None):
        """
        copy&paste of the pretix.base.payment.BasePaymentProvider.payment_form_render
        only to change the template file
        """
        form = self.payment_form(request)
        template = get_template('pretix_eth/checkout_payment_form.html')
        ctx = {'form': form}
        return template.render(ctx, request)

    def checkout_confirm_render(self, request):
        template = get_template("pretix_eth/checkout_payment_confirm.html")
        return template.render({}, request)

    def checkout_prepare(self, request, cart):
        form = self.payment_form(request)

        if form.is_valid():
            self._update_session_payment_amount(request, cart["total"])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            self._update_session_payment_amount(request, payment.amount)
            return True

        return False

    def payment_is_valid_session(self, request):
        return all(
            (
                "payment_amount" in request.session,
                "payment_primary_currency" in request.session,
                "payment_usd_per_eth" in request.session,
                "payment_time" in request.session,
            )
        )

    def _payment_is_valid_info(self, payment: OrderPayment) -> bool:
        return all(
            (
                "amount" in payment.info_data,
                "primary_currency" in payment.info_data,
                "usd_per_eth" in payment.info_data,
                "time" in payment.info_data,
            )
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment.info_data = {
            "amount": request.session["payment_amount"],
            "primary_currency": request.session["payment_primary_currency"],
            "usd_per_eth": request.session["payment_usd_per_eth"],
            "time": request.session["payment_time"],
        }

        payment.save(update_fields=["info"])

    def _update_session_payment_amount(self, request: HttpRequest, total):
        if self.event.currency != "USD":  # TODO support EUR payments
            raise ImproperlyConfigured(
                "The Ethereum payment provider only supports USD denominated events."
            )

        # 1 USD = 10^18 full-precision units of (an abstact logical) stablecoin
        units_per_dollar = 10**18
        payment_amount = int(units_per_dollar * total)

        usd_per_eth = get_eth_price_from_external_apis('USD')

        request.session["payment_amount"] = payment_amount
        request.session["payment_primary_currency"] = self.event.currency
        request.session["payment_usd_per_eth"] = usd_per_eth
        request.session["payment_time"] = int(time.time())

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/pending.html")

        payment_is_valid = self._payment_is_valid_info(payment)
        ctx = {
            "payment_is_valid": payment_is_valid,
            "order": payment.order,
            "payment": payment,
            'event': self.event,
        }

        if not payment_is_valid:
            return template.render(ctx, request)

        ctx["transaction_details_url"] = payment.pk

        latest_signed_message = payment.signed_messages.last()

        submitted_transaction_hash = None
        chain_name = None
        chain_id = None
        receipt_url = None
        order_accepting_payments = True

        if latest_signed_message is not None:
            submitted_transaction_hash = latest_signed_message.transaction_hash
            chain_name = latest_signed_message.chain_name
            chain_id = latest_signed_message.chain_id
            receipt_url = latest_signed_message.receipt_url
            order_accepting_payments = not latest_signed_message.another_signature_submitted

        ctx["submitted_transaction_hash"] = submitted_transaction_hash
        ctx["chain_name"] = chain_name
        ctx["chain_id"] = chain_id
        ctx["receipt_url"] = receipt_url
        ctx["order_accepting_payments"] = order_accepting_payments

        return template.render(ctx, request)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/control.html")

        hex_wallet_address = self.get_receiving_address()

        # display all submitted transaction hashes along with
        # their respective sendr and recipient addresses
        last_signed_message: SignedMessage = payment.signed_messages.last()

        if last_signed_message is not None:
            transaction_sender_address = last_signed_message.sender_address
            transaction_recipient_address = last_signed_message.recipient_address
            transaction_hash = last_signed_message.transaction_hash
            chain_id = last_signed_message.chain_id
            chain_name = last_signed_message.chain_name
            receipt_url = last_signed_message.receipt_url
            token_currency = last_signed_message.token_currency
            token_ticker = last_signed_message.token_ticker
            token_name = last_signed_message.token_name
            token_amount = last_signed_message.token_amount
            token_decimals = last_signed_message.token_decimals
            token_contract_address = last_signed_message.token_contract_address
            is_testnet = last_signed_message.is_testnet
        else:
            transaction_sender_address = None
            transaction_recipient_address = None
            transaction_hash = None
            chain_id = None
            chain_name = None
            receipt_url = None
            token_currency = None
            token_ticker = None
            token_name = None
            token_amount = None
            token_decimals = None
            token_contract_address = None
            is_testnet = None

        ctx = {
            "payment_info": payment.info_data,
            "wallet_address": hex_wallet_address,
            "transaction_sender_address": transaction_sender_address,
            "transaction_recipient_address": transaction_recipient_address,
            "transaction_hash": transaction_hash,
            "chain_id": chain_id,
            "chain_name": chain_name,
            "receipt_url": receipt_url,
            "token_currency": token_currency,
            "token_ticker": token_ticker,
            "token_name": token_name,
            "token_amount": token_amount,
            "token_decimals": token_decimals,
            "token_contract_address": token_contract_address,
            "is_testnet": is_testnet,
        }

        return template.render(ctx, request)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return self.payment_refund_supported(payment)

    def execute_refund(self, refund: OrderRefund):
        raise Exception("Refunds are disabled for this payment provider.")
