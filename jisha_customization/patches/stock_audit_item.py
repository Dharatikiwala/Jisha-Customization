import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({
        "Stock Audit Item": [
            {
                "fieldname": "custom_batch_valuation_rate",
                "label": "Batch Valuation Rate",
                "fieldtype": "Currency",
                "insert_after": "batch",
                "reqd": 0
            }
        ]
    })