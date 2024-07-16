import logging

from django.core.management.base import BaseCommand

from django_scopes import scope

from pretix.base.models import OrderPayment
from pretix.base.models.event import Event

from threecities.v1 import transfer_verification_pb2

from pretix_eth.verifier.verify_payment import verify_payment

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Verify pending orders from on-chain payments. Performs a dry run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-n",
            "--no-dry-run",
            help="Modify database records to confirm payments.",
            action="store_true",
        )
        parser.add_argument(
            '--event-slug',
            help=(
                'The slug of the event for which payments should be confirmed.  '
                'This is used to determine the wallet address to check for '
                'payments. Default: all events.'
            ),
        )

    def handle(self, *args, **options):
        no_dry_run = options["no_dry_run"]
        event_slug = options["event_slug"]
        log_verbosity = int(options.get("verbosity", 0))

        with scope(organizer=None):
            # todo change to events where pending payments are expected only?
            events = Event.objects.all()
            if event_slug is not None:
                events = events.filter(slug=event_slug)

        for event in events:
            self.confirm_payments_for_event(event, no_dry_run, log_verbosity, event_slug)

    def confirm_payments_for_event(self, event: Event, no_dry_run, log_verbosity=0, event_slug=None):
        if not event_slug:
            logger.info(f"Event name - {event.name}")

        with scope(organizer=event.organizer):
            unconfirmed_order_payments = OrderPayment.objects.filter(
                order__event=event,
                state__in=(
                    OrderPayment.PAYMENT_STATE_CREATED,
                    OrderPayment.PAYMENT_STATE_PENDING,
                    # NB here we include canceled OrderPayments such that we attempt to detect and confirm payments for canceled OrderPayments in case the user canceled the OrderPayment after making a valid payment
                    OrderPayment.PAYMENT_STATE_CANCELED,
                ),
            )
            if log_verbosity > 0:
                logger.info(
                    f" * Found {unconfirmed_order_payments.count()} "
                    f"unconfirmed order payments, including OrderPayments that haven't paid yet, and also including canceled OrderPayments"
                )

        for order_payment in unconfirmed_order_payments:
            try:
                if log_verbosity > 0 and order_payment.state != OrderPayment.PAYMENT_STATE_CANCELED and order_payment.signed_messages.all().count() > 0:
                    logger.info(
                        f" * trying to confirm payment: {order_payment} "
                        f"(has {order_payment.signed_messages.all().count()} signed messages)"
                    )
                # it is tempting to put .filter(invalid=False) here, but remember
                # there is still a chance that low-gas txs are mined later on.
                for signed_message in order_payment.signed_messages.all():
                    full_id = order_payment.full_id
                    payment_verified = False
                    try:
                        transfer_verification_request = transfer_verification_pb2.TransferVerificationRequest(
                            trusted=transfer_verification_pb2.TransferVerificationRequest.TrustedData(
                                currency=order_payment.info_data.get('primary_currency'),
                                logical_asset_amount=str(order_payment.info_data.get('amount')),
                                # WARNING this list of tickers should be sourced from plugin config, but right now they are hardcoded into the 3cities interface link, so we also must hardcode them here, and the allowlists in both places must match
                                token_ticker_allowlist=["ETH", "WETH", "DAI"],
                                usd_per_eth=order_payment.info_data.get('usd_per_eth'),
                                receiver_address=signed_message.recipient_address,  # WARNING recipient_address is only trusted field set from plugin config in SignedMessage. TODO consider converting recipient_address in SignedMessage to be untrusted and set this request value from a trusted receiver_address saved into info_data like all other trusted fields
                            ),
                            untrusted_to_be_verified=transfer_verification_pb2.TransferVerificationRequest.UntrustedData(
                                chain_id=signed_message.chain_id,
                                transaction_hash=signed_message.transaction_hash,
                                sender_address=signed_message.sender_address,
                                caip222_style_signature=transfer_verification_pb2.TransferVerificationRequest.SignatureData(
                                    message=signed_message.raw_message,
                                    signature=signed_message.signature,
                                ),
                            )
                        )

                        is_verified = verify_payment(transfer_verification_request)
                        if is_verified:
                            payment_verified = True
                    except Exception as e:
                        logger.error(f"Error verifying payment for order: {order_payment} error: {str(e)}")

                    if payment_verified:
                        if no_dry_run:
                            logger.info(f"  * Confirming order payment {full_id}")
                            with scope(organizer=None):
                                order_payment.confirm()
                            signed_message.is_confirmed = True
                            signed_message.save()
                        else:
                            logger.info(
                                f"  * DRY RUN: Would confirm order payment {full_id}"
                            )
                    else:
                        logger.info(f"No payments found for {full_id}")
            except Exception as e:
                logger.warning(f"An unhandled error occurred for order: {order_payment}")
                logger.warning(e)
