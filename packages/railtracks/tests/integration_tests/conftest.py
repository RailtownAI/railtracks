import pytest
from pathlib import Path
import shutil


@pytest.fixture(scope="session", autouse=True)
def global_teardown():
    # Setup code (before tests run)
    yield
    # Teardown code (after all tests run)
    railtracks_dir = Path(".railtracks")
    if railtracks_dir.exists() and railtracks_dir.is_dir():
        shutil.rmtree(railtracks_dir)
        print("Cleaned up .railtracks directory after tests.")


import asyncio

import railtracks as rt

import random
from datetime import datetime, timedelta

@rt.function_node
async def search_flights():
    await asyncio.sleep(1)
    cities = ["New York", "Los Angeles", "Chicago", "Houston"]
    airlines = [
        "American Airlines",
        "Delta Airlines",
        "United Airlines",
        "Southwest Airlines",
        "British Airways",
        "Air France",
    ]
    flights = []

    for i in range(150):  # Generate 50 flights
        dep_city = random.choice(cities)
        arr_city = random.choice(
            [city for city in cities if city != dep_city]
        )  # Ensure arrival city is different
        departure_time = datetime.now() + timedelta(
            days=random.randint(1, 30), hours=random.randint(0, 23)
        )
        arrival_time = departure_time + timedelta(
            hours=random.randint(1, 6)
        )  # Flight duration between 1-6 hours
        flight = {
            "flight_number": f"{random.choice(['AA', 'DL', 'UA', 'SW', 'BA', 'AF'])}{random.randint(100, 999)}",
            "airline": random.choice(airlines),
            "departure_city": dep_city,
            "arrival_city": arr_city,
            "departure_time": departure_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "arrival_time": arrival_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "price": round(
                random.uniform(100, 1000), 2
            ),  # Price between $100 and $1000
        }
        flights.append(flight)

    return flights


@rt.function_node
def filter_flights(flights: list, departure_city: str, arrival_city: str):
    filtered_flights = [
        flight
        for flight in flights
        if flight["departure_city"] == departure_city
        and flight["arrival_city"] == arrival_city
    ]
    if not filtered_flights:
        raise ValueError(
            f"No outbound flights found from {departure_city} to {arrival_city}."
        )
    return random.choice(filtered_flights)


@rt.function_node
async def pick_flight(flights: list, departure_city: str, arrival_city: str):
    contracts = asyncio.gather(
        rt.call(filter_flights, flights, departure_city, arrival_city),
        rt.call(filter_flights, flights, arrival_city, departure_city),
    )
    outbound, inbound = await contracts

    return {"outbound_flight": outbound, "inbound_flight": inbound}


@rt.function_node
async def book_flight(flight):
    await asyncio.sleep(1)
    return f"Flight {flight['flight_number']} booked from {flight['departure_city']} to {flight['arrival_city']}."


@rt.function_node
async def planner(current_city: str, destination_city: str):
    flights = await rt.call(search_flights)

    flight_plan = await rt.call(pick_flight, flights, current_city, destination_city)

    outbound_booking = await rt.call(book_flight, flight_plan["outbound_flight"])
    inbound_booking = await rt.call(book_flight, flight_plan["inbound_flight"])
    return {"outbound_booking": outbound_booking, "inbound_booking": inbound_booking}


TLLMNode = rt.agent_node(
    system_message="You are excellent chooser of random items from a list. You never make mistakes and have a god like ability to accomplish tasks.",
)

@rt.function_node
async def planner_with_llm(llm: rt.llm.ModelBase):
    cities = []
    available_cities = ["New York", "Chicago", "Los Angeles", "Houston"]
    while True:

        result = await rt.call(
            TLLMNode, 
            user_input=f"Choose a Random city from {available_cities} and give me the index of the city only. Nothing else.",
            llm=llm,
        )  # we will make the mock_llm return a random integer between 0 and 3 to simulate the random choice

        city = available_cities[int(result.text)]
        if city in available_cities:
            available_cities.remove(city)
            cities.append(city)

        if len(cities) == 2:
            break

    return await rt.call(planner, *cities)


@pytest.fixture
def planner_node():
    return planner


@pytest.fixture
def planner_with_llm_node():
    return planner_with_llm


import json


@pytest.fixture
def json_state_schema():
    json_path = Path(__file__).parent / "state_schema.json"
    with open(json_path, "r") as f:
        return json.load(f)
