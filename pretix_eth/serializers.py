from rest_framework.serializers import Serializer, ModelSerializer
from rest_framework import fields

from pretix.base.models import Order

from pretix_eth.models import SignedMessage


class TransactionDetailsSerializer(Serializer):
    amount = fields.CharField()
    primary_currency = fields.CharField()
    usd_per_eth = fields.CharField()
    recipient_address = fields.CharField()
    is_signature_submitted = fields.BooleanField()
    # has_other_unpaid_orders = fields.BooleanField() # TODO rm? see related note in views.py

    _context = None

    def to_representation(self, instance):
        recipient_address = instance.payment_provider.get_receiving_address()

        another_signature_submitted = SignedMessage.objects.filter(
            order_payment__order=instance.order,
            invalid=False
        ).exists()

        # don't let the user pay for multiple order payments within one order
        return {
            "amount": str(instance.info_data.get('amount')),
            "primary_currency": instance.info_data.get('primary_currency'),
            "usd_per_eth": str(instance.info_data.get('usd_per_eth')),
            "recipient_address": recipient_address,
            "is_signature_submitted": another_signature_submitted,
            # "has_other_unpaid_orders": None, # TODO rm? see related note in views.py
            "3cities_interface_domain": instance.payment_provider.get_3cities_interface_domain(),
        }


class PaymentStatusSerializer(ModelSerializer):

    class Meta:
        model = Order
        fields = ('status',)
