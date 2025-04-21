# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

def execute(filters=None):
	if not filters:
		filters = {}
	
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	warehouse = filters.get("warehouse")
	
	columns = [
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": "Warehouse", "fieldname": "warehouse_group", "fieldtype": "Data", "width": 200},
		{"label": "Reorder Level", "fieldname": "reorder_level", "fieldtype": "Float", "width": 140},
		{"label": "Opening Qty", "fieldname": "opening_qty", "fieldtype": "Float", "width": 140},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 140},
		{"label": "Issued Qty", "fieldname": "issued_qty", "fieldtype": "Float", "width": 140},
		{"label": "Ordered Qty", "fieldname": "ordered_qty", "fieldtype": "Float", "width": 150},
		{"label": "Transferred Qty", "fieldname": "transferred_qty", "fieldtype": "Float", "width": 140},
		{"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 150}
	]
	
	data = []
	
	if warehouse:
		items = frappe.db.sql("""
		SELECT i.name, ir.warehouse_group FROM `tabItem` i 
		LEFT JOIN `tabItem Reorders` ir ON ir.parent = i.name 
		WHERE i.disabled = 0 AND ir.reorder_qty IS NOT NULL AND ir.warehouse_group = %s
		""", (warehouse,), as_dict=True)
	else:
		items = frappe.db.sql("""
		SELECT i.name, ir.warehouse_group FROM `tabItem` i 
		LEFT JOIN `tabItem Reorders` ir ON ir.parent = i.name 
		WHERE i.disabled = 0 AND ir.reorder_qty IS NOT NULL
		""", as_dict=True)
	
	if not items:
		frappe.msgprint("No Items Found")
		return columns, data
	
	for item in items:
		reorder_level = get_reorder_level(item.name)
		warehouse_data = get_warehouse_group_list(item.warehouse_group)
		opening_qty = get_closing_qty(item.name, from_date,warehouse_data)
		received_qty = get_received_qty(item.name, from_date, to_date,warehouse_data)
		issued_qty = get_issued_qty(item.name, from_date, to_date,warehouse_data)
		ordered_qty = get_order_qty(item.name, from_date, to_date,warehouse_data)
		transferred_qty = get_transferred_qty(item.name, from_date, to_date,warehouse_data)
		
		balance_qty = (opening_qty + received_qty) - (issued_qty + transferred_qty)
		
		data.append({
			"item_name": item.name,
			"warehouse_group": item.warehouse_group,
			"reorder_level": reorder_level,
			"opening_qty": opening_qty,
			"received_qty": received_qty,
			"issued_qty": issued_qty,
			"ordered_qty": ordered_qty,
			"transferred_qty": transferred_qty,
			"balance_qty": balance_qty
		})
	
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
	qty = frappe.db.sql(
		"""
		SELECT COALESCE(
			(SELECT SUM(pri.qty)
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
			WHERE pri.item_code=%s
			AND pri.warehouse IN %s
			AND pr.posting_date BETWEEN %s AND %s
			AND pr.docstatus = 1),
			0
		) +
		COALESCE(
			(SELECT SUM(sed.qty)
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON sed.parent = se.name
			WHERE sed.item_code=%s 
			AND se.posting_date BETWEEN %s AND %s
			AND sed.t_warehouse IN %s
			AND se.stock_entry_type IN ('Manufacture', 'Material Receipt')
			AND se.docstatus = 1),
			0
		)
		""", (item, tuple(warehouse_data), from_date, to_date, item, from_date, to_date, tuple(warehouse_data)))
	return qty[0][0] if qty and qty[0][0] else 0

def get_issued_qty(item, from_date, to_date, warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT COALESCE(
			(SELECT SUM(sii.qty)
			FROM `tabSales Invoice Item` sii
			INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
			WHERE sii.item_code=%s
			AND sii.warehouse IN %s
			AND si.posting_date BETWEEN %s AND %s
			AND si.update_stock = 1
			AND si.docstatus = 1),
			0
		) +
		COALESCE(
			(SELECT SUM(dni.qty)
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dni.parent = dn.name
			WHERE dni.item_code=%s 
			AND dni.warehouse IN %s    
			AND dn.posting_date BETWEEN %s AND %s
			AND dn.docstatus = 1),
			0
		) +
		COALESCE(
			(SELECT SUM(sed.qty)
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON sed.parent = se.name
			WHERE sed.item_code=%s
			AND sed.s_warehouse IN %s
			AND se.posting_date BETWEEN %s AND %s
			AND se.stock_entry_type = 'Material Issue'
			AND se.docstatus = 1),
			0
		) +
		COALESCE(
			(SELECT SUM(sed.qty)
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON sed.parent = se.name
			WHERE sed.item_code=%s
			AND sed.s_warehouse IN %s
			AND sed.t_warehouse NOT IN %s
			AND se.posting_date BETWEEN %s AND %s
			AND se.stock_entry_type = 'Material Transfer'
			AND se.docstatus = 1),
			0
		)
		""", (
			item, tuple(warehouse_data), from_date, to_date,
			item, tuple(warehouse_data), from_date, to_date,
			item, tuple(warehouse_data), from_date, to_date,
			item, tuple(warehouse_data), tuple(warehouse_data), from_date, to_date
		)
	)
	return qty[0][0] if qty and qty[0][0] else 0
	
def get_order_qty(item, from_date, to_date,warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT SUM(mri.qty) 
		FROM `tabMaterial Request Item` mri
		INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
		WHERE mri.item_code=%s 
		AND mri.warehouse IN %s
		AND mri.schedule_date BETWEEN %s AND %s
		AND mr.material_request_type='Material Transfer'
		AND mr.docstatus = 1
		""", (item, tuple(warehouse_data),from_date, to_date))
	return qty[0][0] if qty and qty[0][0] else 0

def get_transferred_qty(item, from_date, to_date,warehouse_data):
	qty = frappe.db.sql(
		"""
		SELECT SUM(mri.ordered_qty) 
		FROM `tabMaterial Request Item` mri
		INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
		WHERE mri.item_code=%s 
		AND mri.warehouse IN %s
		AND mri.schedule_date BETWEEN %s AND %s
		AND mr.material_request_type='Material Transfer'
		AND mr.docstatus = 1
		AND mr.status IN ('Transferred', 'Partially Received')
		""", (item, tuple(warehouse_data),from_date, to_date))
	return qty[0][0] if qty and qty[0][0] else 0



def get_warehouse_group_list(warehouse_group):
	warehouse_list = frappe.get_all("Warehouse", filters={"parent_warehouse": warehouse_group}, fields=["name"])
	warehouse_list = [wh.name for wh in warehouse_list]

	# Include the warehouse_group itself in the list
	warehouse_list.append(warehouse_group)
	
	return warehouse_list
