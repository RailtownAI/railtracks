from typing import List


def available_locations() -> List[str]:
    """Returns a list of available locations.
    Args:
    Returns:
        List[str]: A list of available locations.
    """
    return [
        "New York",
        "Los Angeles",
        "Chicago",
        "Delhi",
        "Mumbai",
        "Bangalore",
        "Paris",
        "Denmark",
        "Sweden",
        "Norway",
        "Germany",
        "Vancouver",
        "Toronto",
    ]

def currency_used(location: str) -> str:
    """Returns the currency used in a location.
    Args:
        location (str): The location to get the currency used for.
    Returns:
        str: The currency used in the location.
    """
    currency_map = {
        "New York": "USD",
        "Los Angeles": "USD",
        "Chicago": "USD",
        "Delhi": "INR",
        "Mumbai": "INR",
        "Bangalore": "INR",
        "Paris": "EUR",
        "Denmark": "EUR",
        "Sweden": "EUR",
        "Norway": "EUR",
        "Germany": "EUR",
        "Vancouver": "CAD",
        "Toronto": "CAD",
    }
    used_currency = currency_map.get(location)
    if used_currency is None:
        raise ValueError(f"Currency not available for location: {location}")
    return used_currency

def average_location_cost(location: str, num_days: int) -> float:
    """Returns the average cost of living in a location for a given number of days.
    Args:
        location (str): The location to get the cost of living for.
        num_days (int): The number of days for the trip.
    Returns:
        float: The average cost of living in the location.
    """
    daily_costs = {
        "New York": 200.0,
        "Los Angeles": 180.0,
        "Chicago": 150.0,
        "Delhi": 50.0,
        "Mumbai": 55.0,
        "Bangalore": 60.0,
        "Paris": 220.0,
        "Denmark": 250.0,
        "Sweden": 240.0,
        "Norway": 230.0,
        "Germany": 210.0,
        "Vancouver": 200.0,
        "Toronto": 180.0,
    }
    daily_cost = daily_costs.get(location)
    if daily_cost is None:
        raise ValueError(f"Cost information not available for location: {location}")
    return daily_cost * num_days

def convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
    """Converts currency using a static exchange rate (for testing purposes).
    Args:
        amount (float): The amount to convert.
        from_currency (str): The currency to convert from.
        to_currency (str): The currency to convert to.
    Returns:
        float: The converted amount.
    Raises:
        ValueError: If the exchange rate is not available.
    """
    exchange_rates = {
        ("USD", "EUR"): 0.85,
        ("EUR", "USD"): 1.1765,
        ("USD", "INR"): 83.0,
        ("INR", "USD"): 0.01205,
        ("EUR", "INR"): 98.0,
        ("INR", "EUR"): 0.0102,
        ("CAD", "USD"): 0.78,
        ("USD", "CAD"): 1.28,
        ("CAD", "EUR"): 0.66,
        ("EUR", "CAD"): 1.52,
        ("INR", "CAD"): 0.0125,
        ("CAD", "INR"): 80.0,
    }

    rate = exchange_rates.get((from_currency, to_currency))
    if rate is None:
        raise ValueError("Exchange rate not available")
    return amount * rate

