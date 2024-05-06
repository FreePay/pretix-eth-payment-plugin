from django.db import models
from django.utils import timezone

from pretix.base.models import OrderPayment

class SignedMessage(models.Model):
    signature = models.CharField(max_length=132)  # a CAIP-222-style signature provided by the customer to prove they own the wallet address from which their payment transaction was submitted. This prevents an attacker from finding a payment transaction in the mempool or onchain and claiming it was their payment. signature is passed insecurely from the 3cities frontend. "Insecurely" because pretix never verifies this signature. The signature is opaque to pretix and is forwarded to the 3cities verifier for secure verification when confirming the payment
    raw_message = models.TextField()  # the message for which `signature` is the signature. raw_message is passed insecurely from the 3cities frontend and forwarded to the 3cities verifier for secure verification when confirming the payment
    sender_address = models.CharField(max_length=42) # the sending wallet address provided by the customer in raw_message. sender_address provided for pretix administrator convenience only and is not used for payment verification because the 3cities verifier securely extracts sender_address after verifying raw_message. WARNING sender_address must match the sender address contained in raw_message
    # WARNING TODO PROBLEM recipient_address is now a complex type because 3cities supports different receiver addresses on different chains --> how to solve this?
    # today, recipient_address is securely populated from plugin config's singleton receiver address `recipient_address = instance.payment_provider.get_receiving_address()` --> TODO, we want recipient addresses to be configurable in the plugin UI, but we also want python to have only blackbox knowledge of these
    # problems
    #  TODO what's the type of the new receiver address config? maybe default + chainspecific overrides
    #  TODO how does 3cities receive these? --> this is related to idea of how 3cities receives its token/chain config... in a mature SDK, you'd call eg. `3c.setReceiverAddresses(...)`, but instead, we'll need to provide something like `3cities base URL` in plugin config which will include accepted tokens/chains and ?? receiver addresses too? --> it's a big pain point that you can't currently edit generated links because it means you'd have to rebuild the entire generated link to change any of its config, which is brittle and inconvenient --> a proper SDK is by far the best option, it avoids overinvestment in a URL param API, and avoids an immediate need to build capability of editing generated links (which would be extensive brittle code to power the edit because every field in generated link needs to be parsed into its local react state) --> plan
    #   1. start by building receiver addresses into 3cities base URL --> but verifier/model doesn't parse the receiver address from the base url, instead it uses the plugin's configured recipient_address (btw, verifier can return error if provided payment address is an ENS name to keep it simple and reliable... otherwise what if ENS address changes between payment and verification?) --> parsing receiver address out of base url and/or adding a receiver address url param creates extra work because it would temporarily deprecate the plugin's `recipient_address`  here since it's no longer explicitly set. Better to minimize changes by keeping recipient_address as-is... the 3cities base url is then required to coincidentally match this recipient_address until the SDK is implemented in April
    #   2. add chain-specific receiver addresses to CheckoutSettings and serializer
    #   3. then, make a real SDK and deprecate `3cities base URL` in the plugin config such that receiver addresses are manually specified in plugin config and then clientside at runtime, added to a dynamically generated 3cities link using the SDK. --> NB just because we have a mature SDK doesn't mean that token/chain config needs to be specified in the payment plugin... I like the idea of the merchant trusting 3cities to pick appropriate chains/tokens in some cases.
    recipient_address = models.CharField(max_length=42) # the receiving wallet address provided by pretix in the plugin config. recipient_address is passed securely from pretix to the 3cities frontend to collect the payment and then to the 3cities verifier for secure verification when confirming the payment. recipient_address is snapshotted for each order at the time the order is placed so that if the global recipient_address is updated in the plugin config, any older orders won't lose track of the old recipient address to which the customer may have already sent a payment
    transaction_hash = models.CharField(max_length=66, null=True, unique=True) # the transaction hash in which the customer sent payment for this order. transaction_hash is passed insecurely from the 3cities frontend and forwarded to the 3cities verifier for secure verification when confirming the payment. WARNING must be unique to prevent an attacker from "doulble spending" a transaction hash by claiming it as payment for multiple orders
    chain_id = models.IntegerField()  # the chain id on which transaction_hash exists (ie. chain_id is set if and only if transaction_hash has been set). chain_id is passed insecurely from the 3cities frontend and forwarded to the 3cities verifier for secure verification when confirming the payment. Provided only for the convenience of the 3cities verifier and pretix administrators, since the transaction_hash alone is sufficient to identify the chain on which the transaction occurred (by searching all supported chains for it)
    # TODO add block explorer link for admin and user convenience?
    order_payment = models.ForeignKey(
        to=OrderPayment,
        on_delete=models.CASCADE,
        related_name='signed_messages',
    )
    invalid = models.BooleanField(default=False)
    created_at = models.DateTimeField(editable=False, null=True)
    is_confirmed = models.BooleanField(
        default=False)  # true if and only if this payment has been securely confirmed

    def save(self, *args, **kwargs):
        if self.pk is None or self.created_at is None:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def invalidate(self):
        if not self.invalid:
            self.invalid = True
            self.save()

    @property
    def age(self):
        return timezone.now().timestamp() - self.created_at.timestamp()

    @property
    def another_signature_submitted(self):
        if self.order_payment is None:
            return False

        return SignedMessage.objects.filter(
            order_payment__order=self.order_payment.order,
            invalid=False
        ).exists()
