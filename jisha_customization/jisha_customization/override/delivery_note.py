import frappe


def before_save(self, method):
    if self.items:
        # Fetch all items with has_barcode in one query
        item_codes = [row.item_code for row in self.items if row.item_code]
        if item_codes:
            items_with_barcode = frappe.db.get_list(
                "Item",
                filters={"name": ["in", item_codes], "has_barcode": 1},
                pluck="name",
            )
            items_with_barcode_set = set(items_with_barcode)

            for row in self.items:
                if not row.item_code or row.item_code not in items_with_barcode_set:
                    continue

                if not row.custom_barcodes:
                    frappe.throw(
                        title="Missing Barcode",
                        msg=(
                            f"Barcode is mandatory for item "
                            f"<b>{row.item_code}</b> "
                            f"(Row {row.idx}).<br>"
                            f"Please scan or enter a barcode before saving."
                        ),
                    )


def on_submit(self, method):
    if self.items:
        barcodes_to_update = [
            barcode.strip()
            for item in self.items
            if item.custom_barcodes
            for barcode in item.custom_barcodes.split("\n")
        ]
        if barcodes_to_update:
            for barcode in barcodes_to_update:
                if self.is_return:
                    frappe.db.set_value(
                        "Barcode Entry",
                        barcode,
                        "returned_delivery_reference",
                        self.name,
                    )
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Returned")
                else:
                    frappe.db.set_value(
                        "Barcode Entry",
                        barcode,
                        "reference_of_delivery_note",
                        self.name,
                    )
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Delivered")

        boxes_to_update = [
            box.strip()
            for row in self.items
            if row.custom_box_creation_reference_long
            for box in row.custom_box_creation_reference_long.split("\n")
        ]
        for box_name in boxes_to_update:
            if self.is_return:
                frappe.db.set_value(
                    "Box Creation",
                    box_name,
                    "returned_delivery_reference",
                    self.name,
                )
            else:
                frappe.db.set_value(
                    "Box Creation",
                    box_name,
                    "reference_of_delivery_note",
                    self.name,
                )


def on_cancel(self, method):
    if self.items:
        barcodes_to_update = [
            barcode.strip()
            for item in self.items
            if item.custom_barcodes
            for barcode in item.custom_barcodes.split("\n")
        ]
        if barcodes_to_update:
            for barcode in barcodes_to_update:
                if self.is_return:
                    frappe.db.set_value(
                        "Barcode Entry", barcode, "returned_delivery_reference", ""
                    )
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Delivered")
                else:
                    frappe.db.set_value(
                        "Barcode Entry", barcode, "reference_of_delivery_note", ""
                    )
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Active")

        boxes_to_update = [
            box.strip()
            for row in self.items
            if row.custom_box_creation_reference_long
            for box in row.custom_box_creation_reference_long.split("\n")
        ]

        for box_name in boxes_to_update:

            if self.is_return:
                frappe.db.set_value(
                    "Box Creation",
                    box_name,
                    "returned_delivery_reference",
                    "",
                )
            else:
                frappe.db.set_value(
                    "Box Creation",
                    box_name,
                    "reference_of_delivery_note",
                    "",
                )

