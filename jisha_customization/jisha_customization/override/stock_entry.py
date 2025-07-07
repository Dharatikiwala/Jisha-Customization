import frappe
from frappe import _
import json

def on_submit(self,method):

    if self.items and self.stock_entry_type == "Material Transfer":
        for item in self.items:
            if item.custom_barcodes:
                barcodes = [barcode.strip() for barcode in item.custom_barcodes.split("\n") if barcode.strip()]
                for barcode in barcodes:
                    frappe.db.set_value("Barcode Entry", barcode, "warehouse", item.t_warehouse)

def on_cancel(self,method):

    if self.items and self.stock_entry_type == "Material Transfer":
        for item in self.items:
            if item.custom_barcodes:
                barcodes = [barcode.strip() for barcode in item.custom_barcodes.split("\n") if barcode.strip()]
                for barcode in barcodes:
                    frappe.db.set_value("Barcode Entry", barcode, "warehouse", item.s_warehouse)

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
    try:
        doc = json.loads(doc)

        if not doc.get("items"):
            return

        if frappe.db.exists("Barcode Entry", {"reference_of_manufacturing_entry": doc.get("name")}):
            frappe.msgprint(f"A Barcode Entry for {doc.get('name')} has already been created for this Manufacture entry.")
            return

        settings = frappe.get_single("Jisha Settings")
        if not settings.item_group or not settings.qty:
            frappe.msgprint("Please set both Item Group and Additional Qty in Jisha Settings")

        # Get allowed item groups including sub-groups
        allowed_item_groups = {settings.item_group}
        sub_groups = frappe.get_all("Item Group",filters={"parent_item_group": settings.item_group},pluck="name")
        allowed_item_groups.update(sub_groups)

        barcode_entries = []
        for item in doc.get("items"):
            item_group = frappe.db.get_value("Item", item["item_code"], "item_group")
            multiplier = settings.qty if item_group in allowed_item_groups else 1
            final_qty = int(item.get("qty", 0) * multiplier)

            # Only create barcodes for valid finished items (manufacture) or all items (receipt)
            if (doc.get("purpose") == "Manufacture" and item.get("is_finished_item") and item.get("batch_no")) \
               or doc.get("purpose") == "Material Receipt":

                for _ in range(final_qty):
                    barcode_entries.append({
                        "item_code": item["item_code"],
                        "item_qty": 1,
                        "reference_of_manufacturing_entry": doc.get("name"),
                        "manufacturing_date": doc.get("posting_date"),
                        "batch": item.get("batch_no"),
                        "warehouse": item.get("t_warehouse")
                    })

        if not barcode_entries:
            frappe.msgprint(_("No valid barcode entries to create."))
            return

        barcode_entry_refs = []
        for entry in barcode_entries:
            barcode_doc = frappe.new_doc("Barcode Entry")
            barcode_doc.update(entry)
            barcode_doc.insert()
            barcode_entry_refs.append(barcode_doc.name)

        # Group barcode references per item_code + batch
        item_batch_map = {}
        for entry, name in zip(barcode_entries, barcode_entry_refs):
            key = (entry["item_code"], entry["batch"])
            item_batch_map.setdefault(key, []).append(name)

        # Update Stock Entry Detail's custom_barcodes field
        for (item_code, batch), barcodes in item_batch_map.items():
            filters = {
                "parent": doc.get("name"),
                "item_code": item_code
            }
            if batch:
                filters["batch_no"] = batch

            combined_barcodes = "\n".join(barcodes)
            frappe.db.set_value(
                "Stock Entry Detail",
                filters,
                "custom_barcodes",
                combined_barcodes
            )

        frappe.db.commit()
        frappe.msgprint("Barcode entries created successfully.")
        return barcode_entry_refs

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Barcode Entry Creation Failed")
        frappe.throw("An error occurred while creating barcode entries. Please check error logs.")