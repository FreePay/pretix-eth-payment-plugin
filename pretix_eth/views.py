from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404

from pretix.base.models import Order, OrderPayment

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework import permissions, mixins

from pretix_eth import serializers
from pretix_eth.models import SignedMessage

class PaymentTransactionDetailsView(GenericViewSet):
    queryset = OrderPayment.objects.none()
    serializer_class = serializers.TransactionDetailsSerializer
    permission_classes = [permissions.AllowAny]
    permission = 'can_view_orders'
    write_permission = 'can_view_orders'

    def get_queryset(self):
        order = get_object_or_404(Order, code=self.kwargs['order'], event=self.request.event)
        return order.payments.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # TODO rm this code relted to has_other_unpaid_orders? --> see related note in core.js
        # try:
        #     sender_address = request.query_params['sender_address'].lower()
        # except (KeyError, AttributeError):
        #     return HttpResponseBadRequest("Please supply sender_address GET.")

        # has_other_unpaid_orders = SignedMessage.objects.filter(
        #     invalid=False,
        #     sender_address=sender_address,
        #     order_payment__state__in=(
        #         OrderPayment.PAYMENT_STATE_CREATED,
        #         OrderPayment.PAYMENT_STATE_PENDING
        #     )
        # ).exists()

        response_data = serializer.data
        # response_data["has_other_unpaid_orders"] = has_other_unpaid_orders

        return Response(response_data)

    def submit_signed_transaction(self, request, *args, **kwargs):
        order_payment: OrderPayment = self.get_object()
        serializer = self.get_serializer(order_payment)

        sender_address = request.data.get('senderAddress')
        signature = request.data.get('signature')
        message = request.data.get('message')
        transaction_hash = request.data.get('transactionHash').lower()
        chain_id = request.data.get('chainId')

        recipient_address = serializer.data.get('recipient_address')  # WARNING there's a rare race condition here: the recipient_address defined by serializer is sourced from the current plugin config as of this execution. But, the customer has already sent payment to the recipient_address defined at the time the payment config was sent to the 3cities frontend --> how to solve this? Alternatives 1) snapshot the current recipient_address into the customer's order at the time the order is placed. However, this means that updates to recipient_address won't affect old orders that haven't yet paid. There's also no natural DB record in which to snapshot the recipient_address when the order is placed because a SignedMessage doesn't exist for the order until the user has already paid, and there's no other model today that belongs to an order. 2) let the race condition abide. It only occurs if recipient_address is modified between when an order's payment config is sent to the 3cities frontend and when the successful payment details are sent to the backend. In practice, this is a time window measured in ~seconds to ~minutes, and the pretix administrator can simply avoid changing recipient addresses after an event has gone live (or during a burst of ticket sales). 3) snapshot recipient_address into the customer's every time payment details are sent to the frontend; but this creates a new race condition where a customer might pay using one browser tab that had old payment details, but they had opened the payment page in a new tab that snapshotted a new recipient_address --> for now, we'll go with alternative (2) and let this race condition abide because it's rare and knowably avoidable by not updating recipient_address during ticket sales. If it did happen, the payment would fail to verify automatically and then can be manually verified by support

        message_obj = SignedMessage(
            signature=signature,
            raw_message=message,
            sender_address=sender_address,
            recipient_address=recipient_address,
            transaction_hash=transaction_hash,
            chain_id=chain_id,
            order_payment=order_payment,
        )
        message_obj.save()
        return Response(status=201)

class OrderStatusView(mixins.RetrieveModelMixin, GenericViewSet):
    queryset = Order.objects.none()
    serializer_class = serializers.PaymentStatusSerializer
    permission_classes = [permissions.AllowAny]
    permission = 'can_view_orders'
    write_permission = 'can_view_orders'
    lookup_field = 'secret'

    def get_object(self):
        return get_object_or_404(Order, code=self.kwargs['order'], event=self.request.event)
