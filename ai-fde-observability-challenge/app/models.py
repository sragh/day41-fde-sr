from pydantic import BaseModel, Field
from typing import Literal

class CaseApplication(BaseModel):
    case_id: str
    customer_id: str
    amount: float = Field(gt=0)
    country: str
    income: float = Field(gt=0)
    requested_product: str

class CaseDecision(BaseModel):
    case_id: str
    decision: Literal['APPROVE','REJECT','REVIEW']
    risk_score: float
    model_version: str
    reason: str
