import random
import time
import uuid
import datetime
import json
import os
from typing import List, Dict, Any, Union


def create_service_ticket(issue_type: str, location: str) -> Dict[str, str]:
    """
    Creates a mock service ticket for Telus customer support and stores it in telus_tickets.json

    Args:
        issue_type: Type of service issue (e.g., 'internet_outage', 'billing', 'device_support')
        location: Address or postal code where the issue is occurring

    Returns:
        Dictionary containing ticket ID and estimated resolution time
    """
    # Generate a random ticket ID with TELUS prefix
    ticket_id = f"TELUS-{uuid.uuid4().hex[:8].upper()}"

    # Set resolution time based on issue type
    resolution_times = {
        "internet_outage": "24 hours",
        "billing": "48 hours",
        "device_support": "72 hours",
        "tv_service": "48 hours",
        "security_system": "24 hours",
    }

    # Default to 72 hours if issue type not recognized
    estimated_time = resolution_times.get(issue_type.lower(), "72 hours")

    # Create ticket data with more fields for analysis
    current_time = datetime.datetime.now()
    ticket_data = {
        "ticket_id": ticket_id,
        "issue_type": issue_type,
        "location": location,
        "estimated_resolution_time": estimated_time,
        "created_at": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "open",
        "priority": random.choice(["low", "medium", "high", "critical"]),
        "region": extract_region_from_location(location),
    }

    # Store the ticket in the JSON file
    store_ticket(ticket_data)

    # Return basic ticket info as specified in the function signature
    return {"ticket_id": ticket_id, "estimated_resolution_time": estimated_time}


def extract_region_from_location(location: str) -> str:
    """Helper function to extract region from location string"""
    # Simple mock implementation - in real code, would use postal code patterns or address parsing
    location = location.upper()
    if any(code in location for code in ["V", "BC"]):
        return "BC"
    elif any(code in location for code in ["T", "AB"]):
        return "AB"
    elif any(code in location for code in ["M", "L", "K", "N", "ON"]):
        return "ON"
    elif any(code in location for code in ["H", "J", "QC"]):
        return "QC"
    else:
        return "OTHER"


def store_ticket(ticket_data: Dict[str, Any]) -> None:
    """Helper function to store a ticket in the JSON file"""
    filename = "telus_tickets.json"

    try:
        # Read existing tickets if file exists
        if os.path.exists(filename):
            with open(filename, "r") as file:
                tickets = json.load(file)
        else:
            tickets = []

        # Add new ticket
        tickets.append(ticket_data)

        # Write back to file
        with open(filename, "w") as file:
            json.dump(tickets, file, indent=2)

    except Exception as e:
        print(f"Error storing ticket: {e}")


def get_service_tickets(region: str = None, issue_type: str = None, 
                       status: str = None, priority: str = None,
                       created_after: str = None, created_before: str = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieves service tickets from telus_tickets.json with optional filtering parameters
    
    Args:
        region: Filter by region (e.g., 'BC', 'AB', 'ON')
        issue_type: Filter by issue type (e.g., 'internet_outage', 'billing')
        status: Filter by ticket status (e.g., 'open', 'closed')
        priority: Filter by priority level (e.g., 'low', 'medium', 'high', 'critical')
        created_after: Filter tickets created after this date (format: 'YYYY-MM-DD')
        created_before: Filter tickets created before this date (format: 'YYYY-MM-DD')
    
    Returns:
        Dictionary containing a list of ticket dictionaries
    """
    filename = "telus_tickets.json"
    
    try:
        if not os.path.exists(filename):
            return {"tickets": []}
            
        with open(filename, 'r') as file:
            all_tickets = json.load(file)
        
        filtered_tickets = []
        for ticket in all_tickets:
            # Check all filter conditions
            if region is not None and ticket.get("region") != region:
                continue
                
            if issue_type is not None and ticket.get("issue_type") != issue_type:
                continue
                
            if status is not None and ticket.get("status") != status:
                continue
                
            if priority is not None and ticket.get("priority") != priority:
                continue
                
            # Date filtering
            if created_after is not None:
                ticket_date = ticket.get("created_at", "").split()[0]  # Extract date part
                if ticket_date < created_after:
                    continue
                    
            if created_before is not None:
                ticket_date = ticket.get("created_at", "").split()[0]  # Extract date part
                if ticket_date > created_before:
                    continue
            
            # If ticket passed all filters, add it to results
            filtered_tickets.append(ticket)
            
        return {"tickets": filtered_tickets}
            
    except Exception as e:
        print(f"Error retrieving tickets: {e}")
        return {"tickets": []}

def check_network_status(location: str) -> Dict[str, Union[int, float]]:
    """
    Checks the status of Telus network services at a specific location.

    Args:
        location: Address, postal code, or cell tower ID

    Returns:
        Dictionary with network metrics including latency and uptime percentage
    """
    # In a real implementation, this would query actual network monitoring systems
    # Here we'll generate some realistic-looking values

    # Generate a random latency between 15-120ms (lower is better)
    latency = random.randint(15, 120)

    # Generate an uptime percentage (usually very high for telecom)
    uptime = round(random.uniform(97.5, 99.99), 2)

    # Simulate occasional network issues
    if random.random() < 0.05:  # 5% chance of poor metrics
        latency = random.randint(200, 500)
        uptime = round(random.uniform(85.0, 95.0), 2)

    return {"latency_ms": latency, "uptime_percent": uptime}


def get_available_plans(customer_type: str) -> Dict[str, List[Dict[str, Union[str, float, int]]]]:
    """
    Returns a list of available Telus service plans based on customer type.

    Args:
        customer_type: Type of customer ('residential', 'business', 'student')

    Returns:
        Dictionary containing a list of plan dictionaries with plan details
    """
    plans = []

    if customer_type.lower() == "residential":
        plans = [
            {"plan_name": "Internet 75", "price": 89.95, "speed_mbps": 75},
            {"plan_name": "Internet 300", "price": 109.95, "speed_mbps": 300},
            {"plan_name": "Internet Gigabit", "price": 129.95, "speed_mbps": 1000},
            {"plan_name": "Fiber+ Connection", "price": 159.95, "speed_mbps": 1500},
        ]
    elif customer_type.lower() == "business":
        plans = [
            {"plan_name": "Business Internet 150", "price": 129.95, "speed_mbps": 150},
            {"plan_name": "Business Internet 500", "price": 169.95, "speed_mbps": 500},
            {"plan_name": "Business Fiber+", "price": 199.95, "speed_mbps": 1500},
            {"plan_name": "Enterprise Fiber", "price": 299.95, "speed_mbps": 2500},
        ]
    elif customer_type.lower() == "student":
        plans = [
            {"plan_name": "Student Internet 75", "price": 69.95, "speed_mbps": 75},
            {"plan_name": "Student Internet 150", "price": 89.95, "speed_mbps": 150},
        ]
    else:
        # Default to basic residential plans
        plans = [
            {"plan_name": "Internet 75", "price": 89.95, "speed_mbps": 75},
            {"plan_name": "Internet 150", "price": 99.95, "speed_mbps": 150},
        ]

    return {"plans": plans}


def order_device(device_type: str, customer_id: str) -> Dict[str, str]:
    """
    Places a mock order for a device through Telus.

    Args:
        device_type: Type of device (e.g., 'iphone', 'samsung', 'tablet', 'modem')
        customer_id: Customer's unique identifier in Telus system

    Returns:
        Dictionary with order ID and estimated delivery date
    """
    # Generate a random order ID
    order_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"

    # Calculate a delivery date (3-10 business days from now)
    delivery_days = random.randint(3, 10)
    today = datetime.datetime.now()

    # Skip weekends for delivery date calculation
    business_days = 0
    while business_days < delivery_days:
        today += datetime.timedelta(days=1)
        if today.weekday() < 5:  # Monday-Friday (0-4)
            business_days += 1

    delivery_date = today.strftime("%Y-%m-%d")

    return {"order_id": order_id, "delivery_date": delivery_date}


def schedule_installation(service_type: str, address: str) -> Dict[str, str]:
    """
    Books a mock installation appointment for Telus services.

    Args:
        service_type: Type of service installation ('internet', 'tv', 'security', 'smart_home')
        address: Customer's full address

    Returns:
        Dictionary with appointment ID and scheduled date
    """
    # Generate appointment ID
    appointment_id = f"APPT-{uuid.uuid4().hex[:8].upper()}"

    # Calculate available appointment dates (5-15 days in the future)
    days_ahead = random.randint(5, 15)
    appointment_date = datetime.datetime.now() + datetime.timedelta(days=days_ahead)

    # Format date as string
    date_str = appointment_date.strftime("%Y-%m-%d")

    # Add a time slot
    time_slots = ["8:00 AM - 12:00 PM", "1:00 PM - 5:00 PM"]
    time_slot = random.choice(time_slots)

    full_date = f"{date_str} {time_slot}"

    return {"appointment_id": appointment_id, "date": full_date}


def analyze_call_volume(region: str, time_range: str) -> Dict[str, Union[float, List[str]]]:
    """
    Analyzes mock call center volume data for Telus operations.

    Args:
        region: Geographic region ('BC', 'AB', 'ON', etc.)
        time_range: Time period for analysis ('daily', 'weekly', 'monthly')

    Returns:
        Dictionary with average wait time and peak call hours
    """
    # Mock average wait times (in minutes) by region
    region_wait_times = {
        "BC": random.uniform(3.5, 12.0),
        "AB": random.uniform(4.0, 15.0),
        "ON": random.uniform(5.0, 20.0),
        "QC": random.uniform(4.5, 18.0),
        "ATL": random.uniform(3.0, 10.0),
        "PRAIRIES": random.uniform(3.8, 11.5),
    }

    # Default to a moderate wait time for unknown regions
    avg_wait_time = round(region_wait_times.get(region.upper(), random.uniform(5.0, 15.0)), 1)

    # Generate peak hours - typically around lunch and after work
    peak_hour_options = ["10:00-11:00", "11:00-12:00", "12:00-13:00", "16:00-17:00", "17:00-18:00", "18:00-19:00"]

    # Select 2-3 peak hours
    num_peaks = random.randint(2, 3)
    peak_hours = random.sample(peak_hour_options, num_peaks)

    return {"average_wait_time_minutes": avg_wait_time, "peak_hours": peak_hours}


def report_outage(area_code: str) -> Dict[str, str]:
    """
    Reports a mock service outage for a Telus service area.

    Args:
        area_code: Telephone area code or service region code

    Returns:
        Dictionary with outage report ID and estimated fix time
    """
    # Generate outage report ID
    report_id = f"OUTAGE-{area_code}-{uuid.uuid4().hex[:6].upper()}"

    # Generate a random resolution time (1-24 hours)
    resolution_hours = random.randint(1, 24)

    # Calculate estimated fix time
    current_time = datetime.datetime.now()
    fix_time = current_time + datetime.timedelta(hours=resolution_hours)
    estimated_fix = fix_time.strftime("%Y-%m-%d %H:%M")

    return {"outage_report_id": report_id, "estimated_fix_time": estimated_fix}


def translate_customer_message(message: str, language: str) -> Dict[str, str]:
    """
    Mock translation service for customer messages (primarily English<->French).

    Args:
        message: Text message to translate
        language: Target language ('en' for English, 'fr' for French)

    Returns:
        Dictionary with translated message
    """
    # In a real implementation, this would call a translation API
    # This mock version just adds a prefix to simulate translation

    if language.lower() == "fr":
        # Mock English to French by adding "[FR] " prefix
        translated = f"[FR] {message}"
    elif language.lower() == "en":
        # Mock French to English by adding "[EN] " prefix
        translated = f"[EN] {message}"
    else:
        # For other languages, indicate it's a mock translation
        translated = f"[{language.upper()}] {message}"

    # Add a realistic delay to simulate API call
    time.sleep(0.5)

    return {"translated_message": translated}


# Example usage
if __name__ == "__main__":
    # Test ticket creation and retrieval
    print("Creating sample tickets...")
    create_service_ticket("internet_outage", "Vancouver, BC")
    create_service_ticket("billing", "Calgary, AB")
    create_service_ticket("device_support", "Toronto, ON")
    create_service_ticket("internet_outage", "Surrey, BC")
    create_service_ticket("tv_service", "Victoria, BC")

    print("\nRetrieving all tickets:")
    all_tickets = get_service_tickets()
    print(f"Found {len(all_tickets['tickets'])} tickets")

    print("\nRetrieving BC tickets:")
    bc_tickets = get_service_tickets({"region": "BC"})
    print(f"Found {len(bc_tickets['tickets'])} tickets in BC")

    print("\nRetrieving internet outage tickets:")
    outage_tickets = get_service_tickets({"issue_type": "internet_outage"})
    print(f"Found {len(outage_tickets['tickets'])} internet outage tickets")
