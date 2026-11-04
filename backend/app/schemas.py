import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TransactionKind = Literal['income', 'expense']
ExpenseCategory = Literal['Grocery', 'Bills', 'Education', 'Medical', 'EMI / Debt', 'Personal']
Category = Literal['Income', 'Grocery', 'Bills', 'Education', 'Medical', 'EMI / Debt', 'Personal']
EXPENSE_CATEGORIES = ('Grocery', 'Bills', 'Education', 'Medical', 'EMI / Debt', 'Personal')


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    type: TransactionKind
    amount: Decimal = Field(gt=0, le=Decimal('999999999.99'), max_digits=11, decimal_places=2)
    category: Category
    date: date
    description: str | None = Field(default=None, max_length=240)

    @field_validator('date', mode='before')
    @classmethod
    def validate_iso_date(cls, value):
        # Reject numbers, including Unix timestamps, rather than silently converting them.
        if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
            raise ValueError('Date must be a YYYY-MM-DD string')
        return value

    @field_validator('description')
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode='after')
    def check_category(self):
        if self.type == 'income' and self.category != 'Income':
            raise ValueError('Income transactions must use the Income category')
        if self.type == 'expense' and self.category not in EXPENSE_CATEGORIES:
            raise ValueError('Expense transactions require an expense category')
        return self


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    type: TransactionKind
    amount: Decimal
    category: Category
    date: date
    description: str | None
    created_at: datetime
    updated_at: datetime


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class MeOut(BaseModel):
    email: str
    csrf_token: str
