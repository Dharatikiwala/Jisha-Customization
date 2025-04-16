# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

def execute(filters=None):
    if not filters:
        filters = {}
    
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    
    columns = [
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Reorder Level", "fieldname": "reorder_level", "fieldtype": "Float", "width": 140},
        {"label": "Opening Qty", "fieldname": "opening_qty", "fieldtype": "Float", "width": 140},
        {"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 140},
        {"label": "Issued Qty", "fieldname": "issued_qty", "fieldtype": "Float", "width": 140},
        {"label": "Order Received Qty", "fieldname": "order_received_qty", "fieldtype": "Float", "width": 150},
        {"label": "Transferred Qty", "fieldname": "transferred_qty", "fieldtype": "Float", "width": 140},
        {"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 150}
    ]
    
    data = []
    
    items = frappe.get_all("Item", fields=["name"])
    
    for item in items:
        reorder_level = get_reorder_level(item.name)
        opening_qty = get_closing_qty(item.name, from_date)
        received_qty = get_received_qty(item.name, from_date, to_date)
        issued_qty = get_issued_qty(item.name, from_date, to_date)
        order_received_qty = get_order_qty(item.name, from_date, to_date)
        transferred_qty = get_transferred_qty(item.name, from_date, to_date)
        
        balance_qty = (opening_qty + received_qty) - (issued_qty + order_received_qty + transferred_qty)
        
        data.append({
            "item_name": item.name,
            "reorder_level": reorder_level,
            "opening_qty": opening_qty,
            "received_qty": received_qty,
            "issued_qty": issued_qty,
            "order_received_qty": order_received_qty,
            "transferred_qty": transferred_qty,
            "balance_qty": balance_qty
        })
    
    return columns, data

def get_reorder_level(item):
    qty = frappe.db.sql(
        """
        SELECT SUM(reorder_qty) FROM `tabItem Reorders`
        WHERE parent=%s
        """, (item,))
    return qty[0][0] if qty and qty[0][0] else 0

def get_closing_qty(item, date):
    qty = frappe.db.sql(
        """
        SELECT SUM(actual_qty) FROM `tabStock Ledger Entry`
        WHERE item_code=%s AND posting_date < %s
        """, (item, date))
    return qty[0][0] if qty and qty[0][0] else 0

def get_received_qty(item, from_date, to_date):
    
	qty = frappe.db.sql(
		"""
		SELECT COALESCE(
			(SELECT SUM(pri.qty)
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
			WHERE pri.item_code=%s 
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
			AND se.stock_entry_type IN ('Manufacture', 'Material Receipt')
			AND se.docstatus = 1),
			0
		)
		""", (item, from_date, to_date, item, from_date, to_date))
	return qty[0][0] if qty and qty[0][0] else 0

def get_issued_qty(item, from_date, to_date):
	qty = frappe.db.sql(
		"""
		SELECT COALESCE(
			(SELECT SUM(sii.qty)
			FROM `tabSales Invoice Item` sii
			INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
			WHERE sii.item_code=%s 
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
			AND dn.posting_date BETWEEN %s AND %s
			AND dn.docstatus = 1),
			0
		)
		""", (item, from_date, to_date, item, from_date, to_date))
	return qty[0][0] if qty and qty[0][0] else 0

def get_order_qty(item, from_date, to_date):
	qty = frappe.db.sql(
		"""
		SELECT SUM(mri.qty) 
		FROM `tabMaterial Request Item` mri
		INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
		WHERE mri.item_code=%s 
		AND mri.schedule_date BETWEEN %s AND %s
		AND mr.material_request_type='Material Transfer'
		AND mr.docstatus = 1
		""", (item, from_date, to_date))
	return qty[0][0] if qty and qty[0][0] else 0

def get_transferred_qty(item, from_date, to_date):
	qty = frappe.db.sql(
		"""
		SELECT SUM(sed.qty) 
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON sed.parent = se.name
		WHERE sed.item_code=%s 
		AND se.posting_date BETWEEN %s AND %s
		AND se.docstatus = 1
		AND se.stock_entry_type = 'Material Transfer'
		""", (item, from_date, to_date))
	return qty[0][0] if qty and qty[0][0] else 0
