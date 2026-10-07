import csv
from pathlib import Path
from app.observability.tracing import span

DATA = Path(__file__).resolve().parents[2] / 'data' / 'customers.csv'

def get_customer(customer_id: str, trace_id: str, case_id: str):
    with span('customer.lookup', trace_id=trace_id, case_id=case_id, store='customers.csv') as attrs:
        with DATA.open() as f:
            for row in csv.DictReader(f):
                if row['customer_id'] == customer_id:
                    attrs['found'] = True
                    return row
        attrs['found'] = False
    return None
