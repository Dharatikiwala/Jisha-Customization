import frappe
from frappe import _
import json

def on_submit(self,method):

    if self.items and self.stock_entry_type == "Material Transfer":
        for item in self.items:
            # ✅ Handle Barcode Entry update
            if item.custom_barcodes_v1:
                barcodes = [barcode.strip() for barcode in item.custom_barcodes_v1.split("\n") if barcode.strip()]
                for barcode in barcodes:
                    frappe.db.set_value("Barcode Entry", barcode, "warehouse", item.t_warehouse)
            
            # ✅ Handle Box Creation update
            if item.custom_box_reference:
                boxes = [box.strip() for box in item.custom_box_reference.split("\n") if box.strip()]
                for box in boxes:
                    if frappe.db.exists("Box Creation", box):
                        # Fetch child rows (table_mrql)
                        child_rows = frappe.db.get_all(
                            "Barcode Box",
                            filters={"parent": box},
                            fields=["name"]
                        )
                        for row in child_rows:
                            frappe.db.set_value("Barcode Box", row.name, "warehouse", item.t_warehouse)


def on_cancel(self,method):

    if self.items and self.stock_entry_type == "Material Transfer":
        # ✅ Handle Barcode Entry update
        for item in self.items:
            if item.custom_barcodes_v1:
                barcodes = [barcode.strip() for barcode in item.custom_barcodes_v1.split("\n") if barcode.strip()]
                for barcode in barcodes:
                    frappe.db.set_value("Barcode Entry", barcode, "warehouse", item.s_warehouse)

            # ✅ Handle Box Creation update
            if item.custom_box_reference:
                boxes = [box.strip() for box in item.custom_box_reference.split("\n") if box.strip()]
                for box in boxes:
                    if frappe.db.exists("Box Creation", box):
                        # Fetch child rows (table_mrql)
                        child_rows = frappe.db.get_all(
                            "Barcode Box",
                            filters={"parent": box},
                            fields=["name"]
                        )
                        for row in child_rows:
                            frappe.db.set_value("Barcode Box", row.name, "warehouse", item.s_warehouse)

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
            return

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

        # Update Stock Entry Detail's custom_barcodes_v1 field
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
                "custom_barcodes_v1",
                combined_barcodes
            )

        frappe.msgprint("Barcode entries created successfully.")
        return barcode_entry_refs

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Barcode Entry Creation Failed")
        frappe.throw("An error occurred while creating barcode entries. Please check error logs.")



@frappe.whitelist()
def get_items(doc_name):
    get_items = frappe.db.sql("""
        SELECT item_code,
               qty,
               batch_no,
               t_warehouse,
               custom_barcodes_v1,
               LENGTH(custom_barcodes_v1) - LENGTH(REPLACE(custom_barcodes_v1, '\n', '')) + 1 AS barcode_count
        FROM `tabStock Entry Detail`
        WHERE parent = %s
          AND custom_barcodes_v1 IS NOT NULL
          AND (custom_box_reference IS NULL OR custom_box_reference = '')
        ORDER BY idx
    """, doc_name, as_dict=1)

    if not get_items:
        frappe.throw("All items must have boxes created or barcodes do not exist for box creation.")
    return get_items

                             


@frappe.whitelist()
def create_box_creation(item_dict, stock_entry, date):
    try:
        items = json.loads(item_dict)  # Python list of dicts
        created_boxes = []
        created_items = []  # Track items with boxes created

        for item in items:
            divide = int(item.get("divide", 0))
            full_box = int(item.get("full_box", 0))
            item_code = item.get("item_code")
            batch_no = item.get("batch_no")
            warehouse = item.get("warehouse")
            barcode_qty = int(item.get("barcode_qty", 0))
            custom_barcodes_v1 = item.get("custom_barcodes_v1", "")
            remaining_box = float(item.get("remaining_box", 0))
            remaining_barcode = round(remaining_box * divide)

            # Normalize custom_barcodes_v1 into a list (newline-separated in your case)
            if isinstance(custom_barcodes_v1, str):
                barcodes_list = [b.strip() for b in custom_barcodes_v1.split("\n") if b.strip()]
            elif isinstance(custom_barcodes_v1, list):
                barcodes_list = custom_barcodes_v1
            else:
                barcodes_list = []

            # --- Barcode count validation ---
            required_barcode_count = (full_box * divide) + remaining_barcode
            if len(barcodes_list) < required_barcode_count:
                frappe.throw(
                    f"Not enough barcodes provided for item {item_code}. "
                    f"Required: {required_barcode_count}, Provided: {len(barcodes_list)}"
                )

            barcode_index = 0  # Track which barcode we're on
            boxes_for_this_item = []  # Track boxes for this item

            # --- Create full box entries ---
            for _ in range(full_box):
                box_doc = frappe.new_doc("Box Creation")
                box_doc.box_qty = divide
                box_doc.barcode_selection = "Based On Stock Entry"
                box_doc.reference_of_stock_entry = stock_entry

                for _ in range(divide):
                    box_doc.append("table_mrql", {
                        "item_code": item_code,
                        "batch": batch_no,
                        "warehouse": warehouse,
                        "manufacturing_date": date,
                        "barcode_reference": barcodes_list[barcode_index]
                    })
                    barcode_index += 1

                box_doc.insert(ignore_permissions=True)
                box_doc.submit()
                created_boxes.append(box_doc.name)
                boxes_for_this_item.append(box_doc.name)

            # --- Create remaining box entry (if applicable) ---
            if remaining_barcode > 0:
                box_doc = frappe.new_doc("Box Creation")
                box_doc.box_qty = remaining_barcode
                box_doc.barcode_selection = "Based On Stock Entry"
                box_doc.reference_of_stock_entry = stock_entry

                for _ in range(remaining_barcode):
                    box_doc.append("table_mrql", {
                        "item_code": item_code,
                        "batch": batch_no,
                        "warehouse": warehouse,
                        "manufacturing_date": date,
                        "barcode_reference": barcodes_list[barcode_index]
                    })
                    barcode_index += 1

                box_doc.insert(ignore_permissions=True)
                box_doc.submit()
                created_boxes.append(box_doc.name)
                boxes_for_this_item.append(box_doc.name)

            # If any boxes were created for this item, add to created_items list
            if boxes_for_this_item:
                created_items.append({
                    "item_code": item_code,
                    "batch_no":batch_no,
                    "boxes": boxes_for_this_item
                })
                for ci in created_items:
                    box_reference = "\n".join(ci["boxes"])
                    frappe.db.set_value("Stock Entry Detail",{"parent":stock_entry,"item_code":ci["item_code"],"batch_no":ci["batch_no"]},"custom_box_reference",box_reference)

        return {
            "message": f"Created {len(created_boxes)} Box Creation entries",
            "boxes": created_boxes,
            "created_items": created_items
        }
    except:
        frappe.log_error("Box Creation Failed",frappe.get_traceback())
        frappe.throw("An error occurred while creating box creation. Please check error logs.")
