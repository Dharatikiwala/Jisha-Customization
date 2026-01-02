# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def get_data(filters):
    # -------------------------------
    # 1️⃣ Get Stock Entry Types from Settings (with caching)
    # -------------------------------
    settings = frappe.get_cached_doc("Jisha Settings")

    types = [
        row.stock_entry_types
        for row in settings.stock_entry_types
        if row.stock_entry_types
    ]

    if not types:
        frappe.throw("Please configure Stock Entry Types in Jisha Settings")

    # -------------------------------
    # 2️⃣ Define Manufacture Types
    # -------------------------------
    manufacture_types = ("Manufacture", "Viscose Manufacture Entry")

    # -------------------------------
    # 3️⃣ Dynamic Conditions
    # -------------------------------
    conditions = ["se.docstatus = 1"]

    if filters.get("from_date"):
        conditions.append("se.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("se.posting_date <= %(to_date)s")
    if filters.get("item_code"):
        conditions.append("sed.item_code = %(item_code)s")
    if filters.get("item_group"):
        conditions.append("sed.item_group = %(item_group)s")
    if filters.get("warehouse"):
        conditions.append("sed.t_warehouse = %(warehouse)s")
    if filters.get("branch"):
        conditions.append("se.custom_branch = %(branch)s")

    # -------------------------------
    # 4️⃣ Manufacture vs Non-Manufacture Condition
    # -------------------------------
    conditions.append("""(
		(se.stock_entry_type IN %(manufacture_types)s AND sed.is_finished_item = 1)
		OR
		(se.stock_entry_type NOT IN %(manufacture_types)s)
	)""")

    condition_str = " AND ".join(conditions)

    # -------------------------------
    # 5️⃣ Optimized Main Query
    # -------------------------------
    raw_data = frappe.db.sql(
        f"""
		SELECT
			se.stock_entry_type,
			se.name AS stock_entry_name,
			se.work_order,
			se.posting_date,
			sed.item_code,
			sed.t_warehouse,
			sed.valuation_rate,
			sed.qty AS produce_qty,
			sed.item_group,
			sed.batch_no,
			se.custom_branch AS branch,
			COALESCE(wo.qty, sed.qty) AS qty_to_produce
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed 
			ON se.name = sed.parent
		LEFT JOIN `tabWork Order` wo 
			ON se.work_order = wo.name
		WHERE
			se.stock_entry_type IN %(types)s
			AND {condition_str}
		ORDER BY se.posting_date, se.name
	""",
        {**filters, "types": tuple(types), "manufacture_types": manufacture_types},
        as_dict=1,
    )

    # Early return if no data
    if not raw_data:
        return []

    # -------------------------------
    # 6️⃣ Process data based on grouping
    # -------------------------------
    group_by = filters.get("group_by")

    if group_by == "Item Group":
        return _process_grouped_data(raw_data)
    else:
        return _process_ungrouped_data(raw_data)


def _process_ungrouped_data(raw_data):
    """Process data without grouping and add grand total"""
    rows = []
    total_qty_to_produce = 0
    total_produce_qty = 0
    rate_sum = 0
    rate_count = 0

    for row in raw_data:
        qty_to_produce = row.qty_to_produce or 0
        produce_qty = row.produce_qty or 0
        valuation_rate = row.valuation_rate or 0

        rows.append(
            {
                "posting_date": row.posting_date,
                "stock_entry_type": row.stock_entry_type,
                "stock_entry_name": row.stock_entry_name,
                "work_order": row.work_order,
                "item_code": row.item_code,
                "qty_to_produce": qty_to_produce,
                "produce_qty": produce_qty,
                "fg_valuation_rate": valuation_rate,
                "production_item_group": row.item_group,
                "branch": row.branch,
                "warehouse": row.t_warehouse,
                "batch_no": row.batch_no,
                "entry_type": row.stock_entry_type,
            }
        )

        # Accumulate totals
        total_qty_to_produce += qty_to_produce
        total_produce_qty += produce_qty
        if valuation_rate:
            rate_sum += valuation_rate
            rate_count += 1

    # Add grand total
    rows.append(
        {
            "posting_date": "",
            "stock_entry_type": "Grand Total",
            "stock_entry_name": "",
            "work_order": "",
            "item_code": "",
            "qty_to_produce": total_qty_to_produce,
            "produce_qty": total_produce_qty,
            "fg_valuation_rate": rate_sum / rate_count if rate_count else 0,
            "production_item_group": "",
            "branch": "",
            "warehouse": "",
            "batch_no": "",
            "entry_type": "grand_total",
        }
    )

    return rows


def _process_grouped_data(raw_data):
    """Process data with item group grouping"""
    grouped = defaultdict(
        lambda: {
            "rows": [],
            "qty_to_produce": 0,
            "produce_qty": 0,
            "rate_sum": 0,
            "rate_count": 0,
        }
    )

    total_qty_to_produce = 0
    total_produce_qty = 0
    total_rate_sum = 0
    total_rate_count = 0

    # Group and accumulate in one pass
    for row in raw_data:
        item_group = row.item_group
        qty_to_produce = row.qty_to_produce or 0
        produce_qty = row.produce_qty or 0
        valuation_rate = row.valuation_rate or 0

        processed_row = {
            "posting_date": row.posting_date,
            "stock_entry_type": row.stock_entry_type,
            "stock_entry_name": row.stock_entry_name,
            "work_order": row.work_order,
            "item_code": row.item_code,
            "qty_to_produce": qty_to_produce,
            "produce_qty": produce_qty,
            "fg_valuation_rate": valuation_rate,
            "production_item_group": item_group,
            "branch": row.branch,
            "warehouse": row.t_warehouse,
            "batch_no": row.batch_no,
            "entry_type": row.stock_entry_type,
        }

        group_data = grouped[item_group]
        group_data["rows"].append(processed_row)
        group_data["qty_to_produce"] += qty_to_produce
        group_data["produce_qty"] += produce_qty

        if valuation_rate:
            group_data["rate_sum"] += valuation_rate
            group_data["rate_count"] += 1
            total_rate_sum += valuation_rate
            total_rate_count += 1

        total_qty_to_produce += qty_to_produce
        total_produce_qty += produce_qty

    # Build final result
    final_result = []

    for item_group, group_data in grouped.items():
        # Add group rows
        final_result.extend(group_data["rows"])

        # Add subtotal
        final_result.append(
            {
                "posting_date": "",
                "stock_entry_type": "Item Group Total",
                "stock_entry_name": "",
                "work_order": "",
                "item_code": "",
                "qty_to_produce": group_data["qty_to_produce"],
                "produce_qty": group_data["produce_qty"],
                "fg_valuation_rate": (
                    group_data["rate_sum"] / group_data["rate_count"]
                    if group_data["rate_count"]
                    else 0
                ),
                "production_item_group": item_group,
                "branch": "",
                "warehouse": "",
                "batch_no": "",
                "entry_type": "subtotal",
            }
        )

        # Add zero row
        final_result.append(
            {
                "posting_date": "",
                "stock_entry_type": "",
                "stock_entry_name": "",
                "work_order": "",
                "item_code": "",
                "qty_to_produce": 0.00,
                "produce_qty": 0.00,
                "fg_valuation_rate": 0.00,
                "production_item_group": "",
                "branch": "",
                "warehouse": "",
                "batch_no": "",
                "entry_type": "zero_row",
            }
        )

    # Add grand total
    final_result.append(
        {
            "posting_date": "",
            "stock_entry_type": "Grand Total",
            "stock_entry_name": "",
            "work_order": "",
            "item_code": "",
            "qty_to_produce": total_qty_to_produce,
            "produce_qty": total_produce_qty,
            "fg_valuation_rate": total_rate_sum / total_rate_count
            if total_rate_count
            else 0,
            "production_item_group": "",
            "branch": "",
            "warehouse": "",
            "batch_no": "",
            "entry_type": "grand_total",
        }
    )

    return final_result


def get_columns(filters):
    columns = [
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Stock Entry Type",
            "fieldname": "stock_entry_type",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Stock Entry",
            "fieldname": "stock_entry_name",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 120,
        },
        {
            "label": "Work Order",
            "fieldname": "work_order",
            "fieldtype": "Link",
            "options": "Work Order",
            "width": 120,
        },
        {
            "label": "Production Item",
            "fieldname": "item_code",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Qty to Produce",
            "fieldname": "qty_to_produce",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": "Produce Qty",
            "fieldname": "produce_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": "Batch No",
            "fieldname": "batch_no",
            "fieldtype": "Link",
            "options": "Batch",
            "width": 120,
        },
        {
            "label": "FG Valuation Per Rate",
            "fieldname": "fg_valuation_rate",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": "Production Item Group",
            "fieldname": "production_item_group",
            "fieldtype": "Data",
            "width": 250,
        },
        {"label": "Branch", "fieldname": "branch", "fieldtype": "Data", "width": 120},
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Data",
            "width": 220,
        },
    ]

    return columns
