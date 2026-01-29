# zoho_utils.py
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
ZOHO_API_DOMAIN = os.getenv("ZOHO_DOMAIN", "https://www.zohoapis.com")
ZOHO_TOKEN_URL = os.getenv("ZOHO_TOKEN_URL")
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")


_token_cache = {"access_token": None, "expires_at": 0}


def _refresh_access_token(refresh_token: str):
    """
    Refresh Zoho OAuth token if expired.
    """
    global _token_cache
    now = time.time()
    #if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        #return _token_cache["access_token"]

    token_url = ZOHO_TOKEN_URL
    params = {
        "refresh_token": refresh_token,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    r = requests.post(token_url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    access_token = data.get("access_token")
    expires_in = int(data.get("expires_in", 3600))
    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = time.time() + expires_in
    print(access_token);
    return access_token


def _zoho_headers(rt:str):
    token = _refresh_access_token(rt)
    return {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}


# --------------------- Contacts ---------------------
def fetch_all_contacts(refresh_token:str,per_page: int = 200, max_pages: int | None = None):
    """
    Fetch all contacts from Zoho CRM with pagination.
    """
    page = 1
    collected = []
    selected = fetch_org_variable("aileadscore__AI_Weight", refresh_token)
    selected = selected.json()
    fields = selected.get("Contacts",str)
    while True:
        url = f"{ZOHO_API_DOMAIN}/Contacts"
        params = {"page": page, "per_page": per_page, "fields": fields}
        r = requests.get(url, headers=_zoho_headers(refresh_token), params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if not data:
            break
        collected.extend(data)
        if max_pages and page >= max_pages:
            break
        if len(data) < per_page:
            break
        page += 1
    return collected


# --------------------- Leads ---------------------
def fetch_all_leads_from_zoho(refresh_token:str,per_page: int = 200, max_pages: int | None = None):
    """
    Fetch all leads from Zoho CRM with pagination.
    """
    page = 1
    collected = []
    selected = fetch_org_variable("aileadscore__AI_Weight", refresh_token).json()
    fields = selected.get("Leads",str)
    while True:
        url = f"{ZOHO_API_DOMAIN}/Leads"
        params = {"page": page, "per_page": per_page, "fields": fields}
        r = requests.get(url, headers=_zoho_headers(refresh_token), params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if not data:
            break
        collected.extend(data)
        if max_pages and page >= max_pages:
            break
        if len(data) < per_page:
            break
        page += 1
    return collected


def get_lead_from_zoho(refresh_token:str,lead_id: str):
    """
    Fetch a single lead by ID from Zoho CRM.
    """
    url = f"{ZOHO_API_DOMAIN}/Leads/{lead_id}"
    r = requests.get(url, headers=_zoho_headers(refresh_token), timeout=30)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data", [])
    return data[0] if data else {}


def update_zoho_lead_score(refreshToken:str, lead_id: str, score: int, justification: str, recom:str, score_field_name: str = "Lead_Score", jfld:str="AI_Justification", rfld:str="AI_Recommendation"):
    """
    Update a lead score field in Zoho CRM.
    """
    url = f"{ZOHO_API_DOMAIN}/Leads"
    body = {"data": [{"id": str(lead_id), score_field_name: int(score), jfld: str(justification), rfld: str(recom)}]}
    r = requests.put(url, headers=_zoho_headers(refreshToken), json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_org_variable(var_name: str, refresh_token=None):
    url = f"{ZOHO_API_DOMAIN}/org/variables/{var_name}"
    r = requests.get(url, headers=_zoho_headers(refresh_token), timeout=30)
    if r.status_code == 200:
        data = r.json()
        print(data)
        return data.get("Org_Variables", [{}])[0].get("Value")
    return None

def fetch_org_id(refresh_token:str):
    url = f"{ZOHO_API_DOMAIN}/org"
    r = requests.get(url, headers=_zoho_headers(refresh_token), timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("org", [{}])[0].get("zgid")

