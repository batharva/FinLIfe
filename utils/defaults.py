"""Default accounts and categories created for each new user (editable afterwards)."""

def _c(name, cls, essential=False):
    return {"name": name, "financial_classification": cls, "is_essential": essential, "is_default": True}

DEFAULT_CATEGORIES = (
    [_c(n, "need", True) for n in ["Rent or hostel", "Groceries", "Essential meals", "Utilities", "Transportation",
                                  "Education", "Healthcare", "Insurance", "Essential subscriptions"]]
    + [_c(n, "want") for n in ["Restaurants and cafés", "Shopping", "Entertainment", "Gaming", "Travel", "Gadgets",
                              "Hobbies", "Nonessential subscriptions", "Impulse purchases"]]
    + [_c(n, "income") for n in ["Salary", "Internship stipend", "Allowance", "Freelance work", "Interest", "Other income"]]
    + [_c("Emergency fund", "saving"), _c("Bank savings", "saving")]
    + [_c(n, "investment") for n in ["Fixed deposits", "Recurring deposits", "Mutual funds", "Stocks and ETFs",
                                    "Retirement investments"]]
)
DEFAULT_ACCOUNTS = [
    {"account_name": "Bank account", "account_type": "bank", "opening_balance": 0, "currency": "INR"},
    {"account_name": "Cash", "account_type": "cash", "opening_balance": 0, "currency": "INR"},
]
PAYMENT_METHODS = ["UPI", "Cash", "Debit card", "Credit card", "Bank transfer", "Other"]
ACCOUNT_TYPES = {"bank": "Bank account", "cash": "Cash", "wallet": "Wallet", "credit_card": "Credit card",
                 "investment": "Investment account", "other": "Other"}
