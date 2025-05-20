import frappe
import json

def on_submit(self,method):

    if self.items and self.stock_entry_type == "Material Transfer":
        for item in self.items:
            if item.custom_barcodes:
                barcodes = [barcode.strip() for barcode in item.custom_barcodes.split("\n") if barcode.strip()]
                for barcode in barcodes:
                    frappe.db.set_value("Barcode Entry", barcode, "warehouse", item.t_warehouse)
        frappe.db.commit()

def on_cancel(self,method):

    if self.items and self.stock_entry_type == "Material Transfer":
        for item in self.items:
            if item.custom_barcodes:
                barcodes = [barcode.strip() for barcode in item.custom_barcodes.split("\n") if barcode.strip()]
                for barcode in barcodes:
                    frappe.db.set_value("Barcode Entry", barcode, "warehouse", item.s_warehouse)
        frappe.db.commit()

def before_save(self,method):
    entry_type = frappe.db.get_value("Stock Entry Type", self.stock_entry_type,"purpose")

    if not entry_type:
        return

    if entry_type == "Manufacture" and self.from_bom == 1 and self.bom_no:
        calculate_additional_cost(self)

def calculate_additional_cost(self):
    bom_details = frappe.get_doc("BOM", self.bom_no)
    
    if not bom_details.custom_additonal_costs:
        return
        
    self.additional_costs = []
    for ac in bom_details.custom_additonal_costs:
        if ac.amount:
            self.append("additional_costs", {
                "expense_account": ac.expense_account,
                "description": ac.description,
                "amount": ac.amount * self.fg_completed_qty
            })
    
    self.total_additional_costs = sum(t.amount for t in self.get("additional_costs"))


@frappe.whitelist()
def create_barcode_entry(doc):
    
    doc = json.loads(doc)
    if not doc.items:
        return
    
    if frappe.db.exists("Barcode Entry",{"reference_of_manufacturing_entry": doc.get("name")}):
        frappe.msgprint(f"A Barcode Entry for {doc.get('name')} has already been created for this Manufacture entry.")
        return

    barcode_entries = []
    for item in doc.get("items"):
        if item.get("is_finished_item") and item.get("batch_no"):
            barcode_entries.extend([
                {
                    "item_code": item.get("item_code"),
                    "item_qty": 1,
                    "reference_of_manufacturing_entry": doc.get("name"),
                    "manufacturing_date": doc.get("posting_date"),
                    "batch": item.get("batch_no"),
                    "warehouse": item.get("t_warehouse")
                }
                for _ in range(int(item.get("qty", 0)))
            ])

    if barcode_entries:
        try:
            barcode_entry_ref = []
            for entry in barcode_entries:
                barcode_entry = frappe.new_doc("Barcode Entry")
                barcode_entry.update(entry)
                barcode_entry.insert()
                barcode_entry_ref.append(barcode_entry.name)
            
            frappe.msgprint("Barcode entries created successfully.")
            
            # Append each barcode in custom_barcodes with newline separation
            custom_barcodes = "\n".join(barcode_entry_ref)
            frappe.db.set_value(
                "Stock Entry Detail",
                {"parent": doc.get("name"), "is_finished_item": 1},
                "custom_barcodes",
                custom_barcodes
            )
            frappe.db.commit()
            return barcode_entry_ref
        except Exception as e:
            frappe.log_error(f"Barcode Entry Creation failed", frappe.get_traceback())
