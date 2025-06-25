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

	# Join the conditions into SQL WHERE clause
	condition_str = " AND " + " AND ".join(conditions) if conditions else ""

	# --- Viscose Manufacture Entry ---
	viscose_data = frappe.db.sql(f"""
		SELECT 
			MAX(se.posting_date) AS posting_date,
			sed.item_code,
			sed.t_warehouse,
			AVG(sed.valuation_rate) AS valuation_rate,
			SUM(sed.qty) AS qty,
			sed.item_group
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
		WHERE se.stock_entry_type = 'Viscose Manufacture Entry'
			AND sed.is_finished_item = 1
			{condition_str}
		GROUP BY sed.item_code, sed.item_group
	""", filters, as_dict=1)

	for row in viscose_data:
		data.append({
			"posting_date": row.posting_date,
			"item_code": row.item_code,
			"qty_to_produce": row.qty,
			"produce_qty": row.qty,
			"fg_valuation_rate": row.valuation_rate,
			"production_item_group": row.item_group,
			"warehouse":row.t_warehouse,
			"entry_type": "Viscose Manufacture Entry"
		})

	# --- Standard Manufacture Entry ---
	manufacture_data = frappe.db.sql(f"""
		SELECT 
			MAX(se.posting_date) AS posting_date,
			sed.item_code,
			sed.t_warehouse,
			AVG(sed.valuation_rate) AS valuation_rate,
			SUM(sed.qty) AS produce_qty,
			sed.item_group,
			SUM(IFNULL(wo.qty, 0)) AS qty_to_produce
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
		LEFT JOIN `tabWork Order` wo ON se.work_order = wo.name
		WHERE se.stock_entry_type = 'Manufacture'
			AND sed.is_finished_item = 1 AND se.work_order is not NULL
			{condition_str}
		GROUP BY sed.item_code, sed.item_group
	""", filters, as_dict=1)

	for row in manufacture_data:
		data.append({
			"posting_date": row.posting_date,
			"item_code": row.item_code,
			"qty_to_produce": row.qty_to_produce,
			"produce_qty": row.produce_qty,
			"fg_valuation_rate": row.valuation_rate,
			"production_item_group": row.item_group,
			"warehouse":row.t_warehouse,
			"entry_type": "Manufacture"
		})

	return data



def get_columns(filters):

	columns = [
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{"label": "Production Item", "fieldname": "item_code", "fieldtype": "Data", "width": 220},
		{"label": "Qty to Produce", "fieldname": "qty_to_produce", "fieldtype": "Float", "width": 120},
		{"label": "Produce Qty", "fieldname": "produce_qty", "fieldtype": "Float", "width": 120},
		{"label": "FG Valuation Per Rate", "fieldname": "fg_valuation_rate", "fieldtype": "Float", "width": 120},
		{"label": "Production Item Group", "fieldname": "production_item_group", "fieldtype": "Data", "width": 250},
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Data", "width": 220},
	]

	return columns