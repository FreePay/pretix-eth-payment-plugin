import requests
import statistics
import time

api_cache = {}

# List of API endpoints
api_endpoints = [
    "https://api.kraken.com/0/public/Ticker?pair=ETH{currency}",
    "https://api.binance.com/api/v3/ticker/bookTicker?symbol=ETH{currency}",
    "https://api.gemini.com/v1/pubticker/eth{currency}",
    "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies={currency}"
]


def format_api_endpoint(api_endpoint, fiat_currency):
    if fiat_currency == 'USD' and "binance.com" in api_endpoint:
        fiat_currency = 'USDC'

    return api_endpoint.format(currency=fiat_currency)


def fetch_eth_price(api_endpoint, fiat_currency):
    api_endpoint = format_api_endpoint(api_endpoint, fiat_currency)

    # Check if the data is already cached and within the 15-minute window
    if api_endpoint in api_cache:
        cached_data = api_cache[api_endpoint]
        current_time = time.time()
        if current_time - cached_data["timestamp"] <= 900:
            return cached_data["price"]

    try:
        # NB here we set a relatively low timeout for the request, which helps prevent a worst-case long wait experience for the customer whose checkout has triggered the recaching of rates
        response = requests.get(api_endpoint, timeout=10)
        data = response.json()

        # Extract ETH price from each API response based on the endpoint
        if "kraken.com" in api_endpoint:
            eth_price = float(data["result"]["XETHZ" + fiat_currency.upper()]["c"][0])
        elif "binance.com" in api_endpoint:
            eth_price = float(data["bidPrice"])
        elif "gemini.com" in api_endpoint:
            eth_price = float(data["last"])
        elif "coingecko.com" in api_endpoint:
            eth_price = float(data['ethereum'][fiat_currency.lower()])
        else:
            eth_price = None

        if eth_price is not None:
            # Cache the data with the ETH price and timestamp
            api_cache[api_endpoint] = {"price": eth_price, "timestamp": time.time()}

        return eth_price
    except Exception as e:
        print(f"Error fetching data from {api_endpoint}: {e}")
        return None


def get_eth_price_from_external_apis(fiat_currency):
    # Fetch prices from all API endpoints
    eth_prices = [fetch_eth_price(endpoint, fiat_currency) for endpoint in api_endpoints]

    # Filter out None values (indicating errors)
    eth_prices = [price for price in eth_prices if price is not None]

    # Calculate the average price while discarding values that deviate too much
    if eth_prices:
        return round(statistics.median(eth_prices), 2)
    else:
        print("No valid API results to calculate an average.")
        return None
