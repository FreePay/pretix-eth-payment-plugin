from rest_framework.serializers import Serializer, ModelSerializer
from rest_framework import fields

from pretix.base.models import Order

from pretix_eth.models import SignedMessage

class TransactionDetailsSerializer(Serializer):
    currency = fields.CharField()
    recipient_address = fields.CharField()
    amount = fields.CharField()
    is_signature_submitted = fields.BooleanField()
    # has_other_unpaid_orders = fields.BooleanField() # TODO rm? see related note in views.py

    _context = None

    def to_representation(self, instance):
        recipient_address = instance.payment_provider.get_receiving_address()

        another_signature_submitted = SignedMessage.objects.filter(
            order_payment__order=instance.order,
            invalid=False
        ).exists()

        # don't let the user pay for multiple order payments wwithin one order
        return {
            "currency": "USD", # TODO support more currencies and dynamically populate this field
            # TODO include offered ETHUSD exchange rate (or offered ETH amount)
            "recipient_address": recipient_address,
            "amount": str(instance.info_data.get('amount')),
            "is_signature_submitted": another_signature_submitted,
            # "has_other_unpaid_orders": None, # TODO rm? see related note in views.py
        }

class PaymentStatusSerializer(ModelSerializer):

    class Meta:
        model = Order
        fields = ('status',)
