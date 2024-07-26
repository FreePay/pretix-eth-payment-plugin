from django.dispatch import receiver

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import (
    process_response,
)
from pretix.base.signals import (
    register_payment_providers,
    register_data_exporters,
)

from .exporter import EthereumOrdersExporter

@receiver(process_response, dispatch_uid="payment_eth_add_question_type_csp")
def signal_process_response(sender, request, response, **kwargs):
    # TODO: enable js only when question is asked
    # url = resolve(request.path_info)
    h = {}
    if 'Content-Security-Policy' in response:
        h = _parse_csp(response['Content-Security-Policy'])
    _merge_csp(h, {
        'style-src': [
            'https://fonts.googleapis.com',
            "'unsafe-inline'"
        ],
        'img-src': [
            "blob: data:"
        ],
        'script-src': [
            # unsafe-inline/eval required for webpack bundles (we cannot know names in advance).
            "'unsafe-inline'",
            "'unsafe-eval'"
        ],
        'font-src': [
            "https://fonts.gstatic.com"
        ],
        'frame-src': [
            # TODO use get_3cities_interface_domain to set frame-src dynamically instead of including all of 3cities.xyz, staging.3cities.xyz, and staging-prod3.cities.xyz
            'https://3cities.xyz',
            'https://staging-prod.3cities.xyz',
            'https://staging.3cities.xyz',
        ],
        'connect-src': [
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response

@receiver(register_payment_providers, dispatch_uid="payment_eth")
def register_payment_provider(sender, **kwargs):
    from .payment import Ethereum
    return Ethereum

@receiver(register_data_exporters, dispatch_uid='single_event_eth_orders')
def register_data_exporter(sender, **kwargs):
    return EthereumOrdersExporter
