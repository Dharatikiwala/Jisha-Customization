# # Copyright (c) 2025, Akhilam Inc. and contributors
# # For license information, please see license.txt

import frappe
from frappe.utils import getdate


def execute(filters=None):
	if not filters:
		filters = {}
	
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	
	columns = [
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Link", "options":"Item" ,"width": 200},
		{"label": "Warehouse", "fieldname": "warehouse_group", "fieldtype": "Data", "width": 200},
		{"label": "Reorder Level", "fieldname": "reorder_level", "fieldtype": "Float", "width": 140},
		{"label": "Opening Qty", "fieldname": "opening_qty", "fieldtype": "Float", "width": 140},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 140},
		{"label": "Issued Qty", "fieldname": "issued_qty", "fieldtype": "Float", "width": 140},
		{"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 150},
		{"label": "Ordered Qty", "fieldname": "ordered_qty", "fieldtype": "Float", "width": 150},
		{"label": "Transferred Qty", "fieldname": "transferred_qty", "fieldtype": "Float", "width": 140},
		{"label": "Order Balance Qty", "fieldname": "second_balance_qty", "fieldtype": "Float", "width": 150}
	]
	
	# Build query conditions dynamically
	conditions = "i.disabled = 0 AND ir.reorder_qty > 0"
	params = []

	filter_map = {
		"warehouse": "ir.warehouse_group = %s",
		"item_code": "i.name = %s",
		"item_group": "i.item_group = %s"
	}

	# Dynamically add conditions if filters exist
	for filter_key, condition in filter_map.items():
		if filters.get(filter_key):
			conditions += f" AND {condition}"
			params.append(filters.get(filter_key))

	# Construct the final query
	query = f"""
		SELECT 
			i.name, 
			ir.warehouse_group
		FROM `tabItem` i 
		LEFT JOIN `tabItem Reorders` ir ON ir.parent = i.name 
		WHERE {conditions}
	"""

	# Execute query safely
	items = frappe.db.sql(query, tuple(params), as_dict=True)
	
	if not items:
		frappe.msgprint("No Items Found")
		return columns, []
	
	data = []


	condition_apply = frappe.db.get_single_value("Jisha Settings", "auto_reorder_condition")

	for item in items:
		reorder_level = get_reorder_level(item.name)
		warehouse_data = get_warehouse_group_list(item.warehouse_group)

		opening_qty = get_closing_qty(item.name, from_date, warehouse_data)
		received_qty = get_received_qty(item.name, from_date, to_date, warehouse_data)
		issued_qty = get_issued_qty(item.name, from_date, to_date, warehouse_data)
		ordered_qty = get_order_qty(item.name, from_date, to_date, warehouse_data)
		transferred_qty = get_transferred_qty(item.name, from_date, to_date, warehouse_data)

		balance_qty = (opening_qty + received_qty) - issued_qty
		second_balance_qty = ordered_qty - transferred_qty

		# Create the row once (avoid duplication)
		row = {
			"item_name": item.name,
			"warehouse_group": item.warehouse_group,
			"reorder_level": reorder_level,
			"opening_qty": opening_qty,
			"received_qty": received_qty,
			"issued_qty": issued_qty,
			"ordered_qty": ordered_qty,
			"transferred_qty": transferred_qty,
			"balance_qty": balance_qty,
			"second_balance_qty": second_balance_qty
		}

		# Apply condition only if required
		if not condition_apply or second_balance_qty > 0 or (
			second_balance_qty < 0 and reorder_level > balance_qty
		):
			data.append(row)
	
	return columns, data

def get_reorder_level(item):
	qty = frappe.db.sql(
		"""
		SELECT reorder_qty FROM `tabItem Reorders`
		WHERE parent=%s
		""", (item,))
	return qty[0][0] if qty and qty[0][0] else 0

def get_closing_qty(item, date,warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT SUM(actual_qty) FROM `tabStock Ledger Entry`
		WHERE item_code=%s AND posting_date < %s AND warehouse IN %s
		""", (item, date, tuple(warehouse_data)))
	return qty[0][0] if qty and qty[0][0] else 0


def get_received_qty(item, from_date, to_date, warehouse_data):
	try:
		query = """
		SELECT pr.name AS voucher_name, pri.qty AS qty, 'Purchase Receipt' AS type
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		WHERE pri.item_code = %(item)s
		AND pri.warehouse IN %(warehouses)s
		AND pr.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND pr.docstatus = 1

		UNION ALL

		SELECT se.name AS voucher_name, sed.qty AS qty, se.stock_entry_type AS type
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE sed.item_code = %(item)s
		AND sed.t_warehouse IN %(warehouses)s
		AND se.stock_entry_type IN ('Manufacture', 'Material Receipt')
		AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND se.docstatus = 1

		UNION ALL

		SELECT se.name AS voucher_name, sed.qty AS qty, se.stock_entry_type AS type
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE sed.item_code = %(item)s
		AND sed.s_warehouse NOT IN %(warehouses)s
		AND sed.t_warehouse IN %(warehouses)s
		AND se.stock_entry_type = 'Material Transfer'
		AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND se.docstatus = 1

		UNION ALL

		SELECT pi.name AS voucher_name, pii.qty AS qty, 'Purchase Invoice' AS type
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		WHERE pii.item_code = %(item)s
		AND pii.warehouse IN %(warehouses)s
		AND pi.update_stock = 1
		AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND pi.docstatus = 1

		UNION ALL

		SELECT si.name AS voucher_name, abs(sii.qty) AS qty, 'Sales Invoice Return' AS type
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.is_return = 1
		AND sii.item_code = %(item)s
		AND sii.warehouse IN %(warehouses)s
		AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND si.docstatus = 1

		UNION ALL

		SELECT dn.name AS voucher_name, abs(dni.qty) AS qty, 'Delivery Note Return' AS type
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		WHERE dn.is_return = 1
		AND dni.item_code = %(item)s
		AND dni.warehouse IN %(warehouses)s
		AND dn.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND dn.docstatus = 1
		"""

		params = {
			"item": item,
			"warehouses": tuple(warehouse_data),
			"from_date": from_date,
			"to_date": to_date
		}

		data = frappe.db.sql(query, params, as_dict=True)
		total_qty = sum(row.qty for row in data if row.qty)

		return total_qty

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error in get_received_qty")
		return 0


def get_issued_qty(item, from_date, to_date, warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT
		COALESCE((
			SELECT SUM(abs(sii.qty))
			FROM `tabSales Invoice Item` sii
			INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
			WHERE sii.item_code = %s
			AND sii.warehouse IN %s
			AND si.posting_date BETWEEN %s AND %s
			AND si.update_stock = 1
			AND si.docstatus = 1
			AND si.is_return = 0
		), 0) +

		COALESCE((
			SELECT SUM(dni.qty)
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dni.parent = dn.name
			WHERE dni.item_code = %s
			AND dni.warehouse IN %s
			AND dn.posting_date BETWEEN %s AND %s
			AND dn.docstatus = 1
			AND dn.is_return = 0
		), 0) +

		COALESCE((
			SELECT SUM(sed.qty)
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON sed.parent = se.name
			WHERE sed.item_code = %s
			AND sed.s_warehouse IN %s
			AND se.posting_date BETWEEN %s AND %s
			AND se.stock_entry_type = 'Material Issue'
			AND se.docstatus = 1
		), 0) +

		COALESCE((
			SELECT SUM(sed.qty)
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON sed.parent = se.name
			WHERE sed.item_code = %s
			AND sed.s_warehouse IN %s
			AND sed.t_warehouse NOT IN %s
			AND se.posting_date BETWEEN %s AND %s
			AND se.stock_entry_type = 'Material Transfer'
			AND se.docstatus = 1
		), 0) +

		COALESCE((
			SELECT SUM(pri.qty)
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
			WHERE pri.item_code = %s
			AND pri.warehouse IN %s
			AND pr.posting_date BETWEEN %s AND %s
			AND pr.is_return = 1
			AND pr.docstatus = 1
		), 0) +

		COALESCE((
			SELECT SUM(pii.qty)
			FROM `tabPurchase Invoice Item` pii
			INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
			WHERE pii.item_code = %s
			AND pii.warehouse IN %s
			AND pi.posting_date BETWEEN %s AND %s
			AND pi.is_return = 1
			AND pi.update_stock = 1
			AND pi.docstatus = 1
		), 0)
		""",
		(
			# Sales Invoice
			item, tuple(warehouse_data), from_date, to_date,
			# Delivery Note
			item, tuple(warehouse_data), from_date, to_date,
			# Stock Entry - Material Issue
			item, tuple(warehouse_data), from_date, to_date,
			# Stock Entry - Material Transfer (outward)
			item, tuple(warehouse_data), tuple(warehouse_data), from_date, to_date,
			# Purchase Receipt Return
			item, tuple(warehouse_data), from_date, to_date,
			# Purchase Invoice Return
			item, tuple(warehouse_data), from_date, to_date
		)
	)
	return qty[0][0] if qty and qty[0][0] else 0

	
def get_order_qty(item, from_date, to_date, warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT 
			COALESCE((
				SELECT SUM(mri.qty) 
				FROM `tabMaterial Request Item` mri
				INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
				WHERE mri.item_code=%s 
				AND mri.warehouse IN %s
				AND mri.schedule_date BETWEEN %s AND %s
				AND mr.docstatus = 1
			), 0)
			+
			COALESCE((
				SELECT SUM(poi.qty)
				FROM `tabPurchase Order Item` poi
				INNER JOIN `tabPurchase Order` po ON poi.parent = po.name
				WHERE poi.item_code=%s
				AND poi.warehouse IN %s
				AND po.transaction_date BETWEEN %s AND %s
				AND po.docstatus = 1
			), 0)
		""", (
			item, tuple(warehouse_data), from_date, to_date,
			item, tuple(warehouse_data), from_date, to_date
		)
	)
	return qty[0][0] if qty and qty[0][0] else 0

def get_transferred_qty(item, from_date, to_date, warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT 
			COALESCE((
				SELECT SUM(mri.ordered_qty) 
				FROM `tabMaterial Request Item` mri
				INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
				WHERE mri.item_code=%s 
				AND mri.warehouse IN %s
				AND mri.schedule_date BETWEEN %s AND %s
				AND mr.docstatus = 1
				AND mr.status IN ('Transferred', 'Partially Received')
			), 0)
			+
			COALESCE((
				SELECT SUM(pri.qty)
				FROM `tabPurchase Receipt Item` pri
				INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
				WHERE pri.item_code=%s
				AND pri.warehouse IN %s
				AND pr.posting_date BETWEEN %s AND %s
				AND pr.docstatus = 1
			), 0)
		""",
		(
			item, tuple(warehouse_data), from_date, to_date,
			item, tuple(warehouse_data), from_date, to_date
		)
	)
	return qty[0][0] if qty and qty[0][0] else 0



def get_warehouse_group_list(warehouse_group):
	warehouse_list = frappe.get_all("Warehouse", filters={"parent_warehouse": warehouse_group}, fields=["name"])
	warehouse_list = [wh.name for wh in warehouse_list]

	# Include the warehouse_group itself in the list
	warehouse_list.append(warehouse_group)
	
	return warehouse_list