import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("GNS_API_BASE_URL")
API_USER = os.getenv("GNS_API_USER")
API_PASSWORD = os.getenv("GNS_API_PASSWORD")

auth = HTTPBasicAuth(API_USER, API_PASSWORD)


def get_tickets():
    url = f"{BASE_URL}/tickets/"
    response = requests.get(url, auth=auth, timeout=15)
    response.raise_for_status()
    return response.json(), response.status_code


def get_comments():
    url = f"{BASE_URL}/comments/"
    response = requests.get(url, auth=auth, timeout=15)
    response.raise_for_status()
    return response.json(), response.status_code


def get_categories():
    url = f"{BASE_URL}/categories"
    response = requests.get(url, auth=auth, timeout=15)
    response.raise_for_status()
    return response.json(), response.status_code

def post_escalation(payload):
    """
    Registra la escalación como comentario dentro del ticket.
    Endpoint documentado: POST /comments
    Body requerido: idTicket, comment
    """
    url = f"{BASE_URL}/comments"

    response = requests.post(
        url,
        json=payload,
        auth=auth,
        timeout=15
    )

    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}

    return data, response.status_code


