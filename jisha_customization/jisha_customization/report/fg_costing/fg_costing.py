# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_data(filters):
	data = []

	# Dynamic filter conditions
	conditions = []
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
		conditions.append("se.branch = %(branch)s")

	# Join the conditions into SQL WHERE clause
	condition_str = " AND " + " AND ".join(conditions) if conditions else ""

	# --- Viscose Manufacture Entry ---
	viscose_data = frappe.db.sql(f"""
		SELECT 
			se.stock_entry_type,
			se.name AS stock_entry_name,
			se.work_order,
			se.posting_date,
			sed.item_code,
			sed.t_warehouse,
			sed.valuation_rate,
			sed.qty,
			sed.item_group,
			se.custom_branch as branch
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
		WHERE se.stock_entry_type = 'Viscose Manufacture Entry'
			AND sed.is_finished_item = 1 AND se.docstatus < 2
			{condition_str}
	""", filters, as_dict=1)

	for row in viscose_data:
		data.append({
			"stock_entry_type": row.stock_entry_type,
			"stock_entry_name": row.stock_entry_name,
			"work_order": row.work_order,
			"branch": row.branch,
			"posting_date": row.posting_date,
			"item_code": row.item_code,
			"qty_to_produce": row.qty,
			"produce_qty": row.qty,
			"fg_valuation_rate": row.valuation_rate,
			"production_item_group": row.item_group,
			"warehouse": row.t_warehouse,
			"entry_type": "Viscose Manufacture Entry"
		})

	# --- Standard Manufacture Entry ---
	manufacture_data = frappe.db.sql(f"""
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
			IFNULL(wo.qty, 0) AS qty_to_produce,
			se.custom_branch as branch
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
		LEFT JOIN `tabWork Order` wo ON se.work_order = wo.name
		WHERE se.stock_entry_type = 'Manufacture'
			AND sed.is_finished_item = 1 AND se.work_order is not NULL  AND se.docstatus < 2
			{condition_str}
	""", filters, as_dict=1)

	for row in manufacture_data:
		data.append({
			"stock_entry_type": row.stock_entry_type,
			"stock_entry_name": row.stock_entry_name,
			"work_order": row.work_order,
			"branch": row.branch,
			"posting_date": row.posting_date,
			"item_code": row.item_code,
			"qty_to_produce": row.qty_to_produce,
			"produce_qty": row.produce_qty,
			"fg_valuation_rate": row.valuation_rate,
			"production_item_group": row.item_group,
			"warehouse": row.t_warehouse,
			"entry_type": "Manufacture"
		})

	# --- Total Row ---
	total_qty_to_produce = sum(d.get("qty_to_produce", 0) or 0 for d in data)
	total_produce_qty = sum(d.get("produce_qty", 0) or 0 for d in data)
	valid_rates = [d.get("fg_valuation_rate", 0) for d in data if d.get("fg_valuation_rate") not in (None, 0)]
	average_rate = sum(valid_rates) / len(valid_rates) if valid_rates else 0

	data.append({
		"posting_date":"",
		"stock_entry_type": "Total",
		"stock_entry_name": "",
		"work_order": "",
		"item_code": "",
		"qty_to_produce": total_qty_to_produce,
		"produce_qty": total_produce_qty,
		"fg_valuation_rate": average_rate,
		"production_item_group": "",
		"branch": "",
		"warehouse": "",
		"entry_type": "",
	})

	return data


def get_columns(filters):

	columns = [
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{"label": "Stock Entry Type", "fieldname": "stock_entry_type", "fieldtype": "Data", "width": 150},
		{"label": "Stock Entry", "fieldname": "stock_entry_name", "fieldtype": "Link","options":"Stock Entry","width": 120},
		{"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options":"Work Order", "width": 120},
		{"label": "Production Item", "fieldname": "item_code", "fieldtype": "Data", "width": 220},
		{"label": "Qty to Produce", "fieldname": "qty_to_produce", "fieldtype": "Float","precision":2, "width": 120},
		{"label": "Produce Qty", "fieldname": "produce_qty", "fieldtype": "Float","precision":2, "width": 120},
		{"label": "FG Valuation Per Rate", "fieldname": "fg_valuation_rate", "fieldtype": "Float","precision":2, "width": 120},
		{"label": "Production Item Group", "fieldname": "production_item_group", "fieldtype": "Data", "width": 250},
		{"label": "Branch", "fieldname": "branch", "fieldtype": "Data", "width": 120},
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Data", "width": 220},
		
	]

	return columns