# Pretix Ethereum Payment Provider

## What is this

This is an Ethereum payment plugin for [pretix](https://github.com/pretix/pretix). This plugin sends and verifies the payment using [3cities](https://3cities.xyz/).

## Development setup

1. Clone this repository, e.g. to `local/pretix-eth-payment-plugin`.
1. Create and activate a virtual environment.
1. Execute `pip install -e .[dev]` within the `pretix-eth-payment-plugin` repo
   directory.
1. Setup a local database by running `make devmigrate`.
1. Fire up a local dev server by running `make devserver`.
1. Visit http://localhost:8000/control/login in a browser windows and enter
   username `admin@localhost` and password `admin` to log in.
1. Enter "Admin mode" by clicking the "Admin mode" text in the upper-right
   corner of the admin interface to create a test organization and event.
1. Follow instructions in [Event Setup Instructions](#event-setup-instructions)
1. If you need to update clientside js code, this happens in [the web3modal folder](pretix_eth/web3modal/README.md) - check the README there.

## Event Setup Instructions
1. Under the event, go to Settings -> Plugins -> Payment Providers -> click on Enable under "Pretix Ethereum Payment Provider" 
2. Next, under Settings, go to Payments -> "Pay on Ethereum" -> Settings -> click on "enable payment method". 
3. Next, scroll down and set the values for the following:
  - "Payment receiver address" - Ethereum address at which all payments will be sent to

You can now play with the event by clicking on the "Go to Shop" button at the top left (next to the event name)

## 3cities setup

### 3cities payment client
TODO

### Run payment verifier gRPC service
TODO

## Automatic payment confirmation with the `confirm_payments` command

This plugin includes a [django management command](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/#module-django.core.management) that can be used to automatically confirm orders from the Ethereum address associated with each order across all events. By default, this command will perform a dry run which only displays payment records that would be modified and why but without actually modifying them.  

Here's an example invocation of this command:
```bash
python -mpretix confirm_payments \
    --no-dry-run
```
Note that this doesn't require you to pass any event slug, since it runs for all events at once. It inspects the address that was associated with each order (at
the time the ticket was reserved) to determine if sufficient payments were made
for the order.  It may check for an ethereum payment or some kind of token
payment depending on what was chosen during the checkout process. It checks using the RPC URLs that were configured in the admin settings while setting up the event. If no rpc urls were set, then the command gives yet another chance to type in a rpc url (like infura). The `--no-dry-run` flag directs the command to
update order statuses based on the checks that are performed.  Without this
flag, the command will only display how records would be modified. 

For more details about the `confirm_payments` command and its options, the
command may be invoked with `--help`:
```bash
python -mpretix confirm_payments --help
```

## History

It started with [ligi](https://ligi) suggesting [pretix for Ethereum
Magicians](https://ethereum-magicians.org/t/charging-for-tickets-participant-numbers-event-ticketing-for-council-of-paris-2019/2321/2).

Then it was used for Ethereum Magicians in Paris (shout out to
[boris](https://github.com/bmann) for making this possible) - but accepting ETH
or DAI was a fully manual process there.

Afterwards boris [put up some funds for a gitcoin
bounty](https://github.com/spadebuilders/community/issues/30) to make a plugin
that automates this process. And [nanexcool](https://github.com/nanexcool)
increased the funds and added the requirement for DAI.

The initial version was developed by [vic-en](https://github.com/vic-en) but he
vanished from the project after cashing in the bounty money and left the plugin
in a non-working state.

Then the idea came up to use this plugin for DevCon5 and the plugin was forked
to this repo and [ligi](https://ligi.de), [david
sanders](https://github.com/davesque), [piper
meriam](https://github.com/pipermerriam), [rami](https://github.com/raphaelm),
[Pedro Gomes](https://github.com/pedrouid), and [Jamie
Pitts](https://github.com/jpitts) brought it to a state where it is usable for
DevCon5 (still a lot of work to be done to make this a good plugin). Currently,
it is semi-automatic. But it now has ERC-681 and Web3Modal
support. If you want to dig a bit into the problems that emerged short before
the launch you can have a look at [this
issue](https://github.com/esPass/pretix-eth-payment-plugin/pull/49)

For DEVcon6 the plugin was extended with some more features like [Layer2 support by Rahul](https://github.com/rahul-kothari). Layer2 will play a significant [role in Ethereum](https://ethereum-magicians.org/t/a-rollup-centric-ethereum-roadmap/4698). Unfortunately DEVcon6 was delayed due to covid - but we where able to use and this way test via the [LisCon](https://liscon.org) ticket sale. As far as we know this was the first event ever offering a Layer2 payment option.
In the process tooling like [Web3Modal](https://github.com/Web3Modal/web3modal/) / [Checkout](https://github.com/Web3Modal/web3modal-checkout) that we depend on was improved.

For Devconnect IST an effort was made to improve the plugin in a variety of ways: WalletConnect support, single receiver mode (accept payments using just one wallet), more networks, automatic ETH rate fetching, improved UI and messaging, and smart contract wallet support. All of these features made it into this version of the plugin, except for smart contract wallet support - issues processing transactions stemming from sc wallets meant that we ultimately had to turn away sc wallet payments altogether.

For Devcon 7, 3cities was [adopted](https://github.com/efdevcon/DIPs/blob/master/DIPs/DIP-37.md) for ticket payments. 3cities is a decentralized, open-source offchain payment processor to help abstract over wallets, chains, tokens, currencies, and payment methods.