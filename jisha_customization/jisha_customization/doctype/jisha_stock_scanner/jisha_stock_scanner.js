// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Jisha Stock Scanner", {
    refresh(frm) {
        frm.set_query("warehouse", function () {
            return {
                filters: {
                    "is_group": 0
                }
            }
        });

        // Set child table query filters
        frm.set_query("warehouse", "items", function () {
            return {
                filters: {
                    "is_group": 0
                }
            }
        });

        frm.add_custom_button(__('Clear Form'), function () {
            clear_all_fields(frm);
        });

        frm.add_custom_button("Create Stock Audit", function () {
            frappe.call({
                method: "jisha_customization.jisha_customization.doctype.jisha_stock_scanner.jisha_stock_scanner.create_stock_audit",
                args: {
                    "doc": frm.doc
                },
                freeze: true,
                freeze_message: __("Creating Stock Audit..."),
                callback: function (r) {
                    if (r.message) {
                        if (r.message.status === "success") {
                            frappe.msgprint({
                                title: __("Success"),
                                indicator: "green",
                                message: r.message.message
                            });
                        } else if (r.message.status === "error") {
                            frappe.msgprint({
                                title: __("Error"),
                                indicator: "red",
                                message: r.message.message
                            });
                        }
                    } else {
                        frappe.msgprint({
                            title: __("Error"),
                            indicator: "red",
                            message: __("Unexpected response from server.")
                        });
                    }
                }
            });
        });
    },

    warehouse: function (frm) {
        // When parent target warehouse changes, update Target Warehouse for all rows
        if (frm.doc.warehouse && frm.doc.items && frm.doc.items.length > 0) {
            frm.doc.items.forEach(d => {
                frappe.model.set_value(d.doctype, d.name, "warehouse", frm.doc.warehouse);
            });
            frm.refresh_field("items");
        }
    },

    scan_barcode: function (frm) {
        if (frm.doc.scan_barcode) {
            frappe.call({
                method: "jisha_customization.jisha_customization.doctype.jisha_stock_scanner.jisha_stock_scanner.get_barcode_data",
                args: {
                    "barcode_data": frm.doc.scan_barcode,
                },
                callback: function (res) {
                    if (res && res.message) {
                        let barcode_data = res.message;
                        let items = frm.doc.items || [];

                        if (barcode_data.status === 'error') {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: barcode_data.message
                            });
                            frm.set_value("scan_barcode", "");
                            return;
                        }

                        // Show warnings if the barcode is sold/delivered, but still proceed
                        if (barcode_data.warning) {
                            frappe.show_alert({
                                message: barcode_data.warning,
                                indicator: 'orange'
                            });
                        }

                        let target_item_code = "";
                        let system_warehouse = "";
                        let scan_qty = 0;
                        let barcode_names = [];
                        let box_names = [];
                        let batches = [];

                        if (barcode_data.doctype === "Barcode Entry") {
                            target_item_code = barcode_data.item_code;
                            system_warehouse = barcode_data.warehouse;
                            scan_qty = barcode_data.item_qty || barcode_data.qty || 1;
                            barcode_names.push(barcode_data.name);
                            if (barcode_data.reference_of_box) {
                                box_names.push(barcode_data.reference_of_box);
                            }
                            if (barcode_data.batch) {
                                batches.push(barcode_data.batch);
                            }
                        } else if (barcode_data.doctype === "Box Creation") {
                            let child_data = barcode_data.table_mrql || [];
                            if (child_data.length === 0) {
                                frappe.msgprint(__('Box is empty or has no child barcodes.'));
                                frm.set_value("scan_barcode", "");
                                return;
                            }
                            target_item_code = child_data[0].item_code;
                            system_warehouse = child_data[0].warehouse;
                            scan_qty = barcode_data.box_qty || 0;
                            box_names.push(barcode_data.name);

                            child_data.forEach(cd => {
                                if (cd.barcode_reference) {
                                    barcode_names.push(cd.barcode_reference);
                                }
                                if (cd.batch && !batches.includes(cd.batch)) {
                                    batches.push(cd.batch);
                                }
                            });
                        }

                        // 🔍 Check for duplicate scans globally across all rows
                        let duplicateRow = null;
                        if (barcode_data.doctype === "Barcode Entry") {
                            duplicateRow = items.find(r => {
                                let existing_barcodes = (r.barcodes || "").split("\n").filter(Boolean);
                                return existing_barcodes.includes(barcode_data.name);
                            });
                        } else if (barcode_data.doctype === "Box Creation") {
                            duplicateRow = items.find(r => {
                                let existing_barcodes = (r.barcodes || "").split("\n").filter(Boolean);
                                let existing_boxes = (r.boxes || "").split("\n").filter(Boolean);
                                return existing_boxes.includes(barcode_data.name) ||
                                       barcode_names.some(name => existing_barcodes.includes(name));
                            });
                        }

                        if (duplicateRow) {
                            frappe.msgprint({
                                title: __('Duplicate Scan'),
                                indicator: 'red',
                                message: __(
                                    "Scanned Barcode/Box already exists in Row #{0} (Item: {1}).",
                                    [duplicateRow.idx, duplicateRow.item_code]
                                )
                            });
                            frm.set_value("scan_barcode", "");
                            return;
                        }

                        // Determine the Target Warehouse for the row
                        let target_warehouse = frm.doc.warehouse || system_warehouse;

                        // Call server to fetch stock details for the system warehouse (old warehouse)
                        frappe.call({
                            method: "jisha_customization.jisha_customization.doctype.jisha_stock_scanner.jisha_stock_scanner.get_item_stock_details",
                            args: {
                                item_code: target_item_code,
                                warehouse: system_warehouse,
                                batch_no: batches.join("\n")
                            },
                            callback: function (r) {
                                if (r.message) {
                                    let warehouse_qty = r.message.warehouse_qty || 0;
                                    let batch_valuation_rate = r.message.batch_valuation_rate || 0.0;

                                    // 🔍 Look for a row with same item code, target warehouse, batch, and box reference
                                    let row = items.find(d => {
                                        if (d.item_code !== target_item_code || d.warehouse !== target_warehouse) return false;
                                        if (!d.barcode_qty) return false;

                                        // Match batches
                                        let row_batches = (d.batch || "").split("\n").filter(Boolean);
                                        let has_batch_match = batches.length === 0 && row_batches.length === 0;
                                        if (batches.length > 0 && row_batches.length > 0) {
                                            has_batch_match = batches.some(b => row_batches.includes(b));
                                        }
                                        if (!has_batch_match) return false;

                                        // Match boxes
                                        let row_boxes = (d.boxes || "").split("\n").filter(Boolean);
                                        let has_box_match = box_names.length === 0 && row_boxes.length === 0;
                                        if (box_names.length > 0 && row_boxes.length > 0) {
                                            has_box_match = box_names.some(b => row_boxes.includes(b));
                                        }
                                        return has_box_match;
                                    });

                                    // If not found, look for any empty row for this item and warehouse
                                    if (!row) {
                                        row = items.find(d => d.item_code === target_item_code && d.warehouse === target_warehouse && !d.barcode_qty);
                                    }

                                    if (!row) {
                                        // Create a new child row
                                        row = frm.add_child("items", {
                                            item_code: target_item_code,
                                            system_warehouse: system_warehouse,
                                            warehouse: target_warehouse,
                                            warehouse_qty: warehouse_qty,
                                            barcode_qty: 0,
                                            variance_qty: 0,
                                            batch_valuation_rate: batch_valuation_rate
                                        });
                                    }

                                    // Calculate updated values
                                    let new_barcode_qty = (row.barcode_qty || 0) + scan_qty;
                                    let new_variance_qty = (row.warehouse_qty || 0) - new_barcode_qty;

                                    // Update barcodes list
                                    let current_barcodes = (row.barcodes || "").split("\n").filter(Boolean);
                                    barcode_names.forEach(name => {
                                        if (!current_barcodes.includes(name)) {
                                            current_barcodes.push(name);
                                        }
                                    });

                                    // Update boxes list
                                    let current_boxes = (row.boxes || "").split("\n").filter(Boolean);
                                    box_names.forEach(name => {
                                        if (!current_boxes.includes(name)) {
                                            current_boxes.push(name);
                                        }
                                    });

                                    // Update batches list
                                    let current_batches = (row.batch || "").split("\n").filter(Boolean);
                                    batches.forEach(b => {
                                        if (!current_batches.includes(b)) {
                                            current_batches.push(b);
                                        }
                                    });

                                    // Use frappe.model.set_value to correctly update all fields
                                    frappe.model.set_value(row.doctype, row.name, {
                                        barcode_qty: new_barcode_qty,
                                        variance_qty: new_variance_qty,
                                        barcodes: current_barcodes.join("\n"),
                                        boxes: current_boxes.join("\n"),
                                        batch: current_batches.join("\n")
                                    });

                                    frappe.show_alert({
                                        message: `Barcode added to Row ${row.idx} (Item: ${row.item_code})`,
                                        indicator: 'green'
                                    });

                                    frm.set_value("scan_barcode", "");
                                    frm.refresh_field("items");
                                    frm.save();
                                }
                            }
                        });
                    }
                }
            });
        }
    }
});

function clear_all_fields(frm) {
    // Clear all child tables
    frm.doc.fields_dict && Object.keys(frm.doc.fields_dict).forEach(fieldname => {
        let field = frm.fields_dict[fieldname];
        if (field && field.df.fieldtype === "Table") {
            frm.clear_table(fieldname);
        }
    });

    // Clear all normal fields
    $.each(frm.fields_dict, function (fieldname, field) {
        if (field.df.fieldtype !== "Button" &&
            field.df.fieldtype !== "Section Break" &&
            field.df.fieldtype !== "Column Break" &&
            field.df.fieldtype !== "Date" &&
            field.df.fieldtype !== "HTML") {
            frm.set_value(fieldname, null);
        }
    });

    frm.refresh_fields();
    frm.save();
    frappe.show_alert({ message: __("Form cleared successfully"), indicator: "green" });
}
