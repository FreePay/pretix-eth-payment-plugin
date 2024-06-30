import logging

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope

from pretix.base.models import OrderPayment
from pretix.base.models.event import Event

# from pretix_eth.verifier.verify_payment import verify_payment

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

    def handle(self, *args, **options):
        no_dry_run = options["no_dry_run"]
        log_verbosity = int(options.get("verbosity", 0))

        with scope(organizer=None):
            # todo change to events where pending payments are expected only?
            events = Event.objects.all()

        for event in events:
            self.confirm_payments_for_event(event, no_dry_run, log_verbosity)

    def confirm_payments_for_event(self, event: Event, no_dry_run, log_verbosity=0):
        logger.info(f"Event name - {event.name}")

        with scope(organizer=event.organizer):
            unconfirmed_order_payments = OrderPayment.objects.filter(
                order__event=event,
                state__in=(
                    OrderPayment.PAYMENT_STATE_CREATED,
                    OrderPayment.PAYMENT_STATE_PENDING,
                    OrderPayment.PAYMENT_STATE_CANCELED,
                ),
            )
            if log_verbosity > 0:
                logger.info(
                    f" * Found {unconfirmed_order_payments.count()} "
                    f"unconfirmed order payments"
                )

        for order_payment in unconfirmed_order_payments:
            try:
                if log_verbosity > 0:
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
                        # TODO real request/response types and check response type for verification success
                        # verify_payment()
                        payment_verified = True
                    except Exception as e:
                        logger.error(f"Error verifying payment for order: {order_payment}")

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
