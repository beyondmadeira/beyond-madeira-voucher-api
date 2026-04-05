import requests
from flask import current_app


def _headers():
    token = current_app.config["AIRTABLE_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def airtable_list(base_id, table_name, max_records=1000, params=None):
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table_name)}"
    records = []
    offset = None
    while True:
        p = {"pageSize": 100}
        if offset:
            p["offset"] = offset
        if params:
            p.update(params)
        r = requests.get(url, headers=_headers(), params=p, timeout=15)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        if len(records) >= max_records:
            break
        offset = data.get("offset")
        if not offset:
            break
    return records


def airtable_patch(base_id, table_name, record_id, fields):
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table_name)}/{record_id}"
    r = requests.patch(url, headers=_headers(), json={"fields": fields}, timeout=15)
    r.raise_for_status()
    return r.json()


def airtable_create(base_id, table_name, fields):
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table_name)}"
    r = requests.post(url, headers=_headers(), json={"fields": fields}, timeout=15)
    r.raise_for_status()
    return r.json()


def airtable_delete(base_id, table_name, record_id):
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table_name)}/{record_id}"
    r = requests.delete(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def airtable_batch_patch(base_id, table_name, records_data):
    """Patch up to 10 records in a single request."""
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table_name)}"
    r = requests.patch(
        url,
        headers=_headers(),
        json={"records": records_data},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
