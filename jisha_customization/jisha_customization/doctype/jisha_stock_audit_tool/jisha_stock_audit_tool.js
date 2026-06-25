// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Jisha Stock Audit Tool", {
    refresh(frm) {
        frm.set_query("warehouse", function () {
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
                method: "jisha_customization.jisha_customization.doctype.jisha_stock_audit_tool.jisha_stock_audit_tool.create_stock_audit",
                args: {
                    "doc": frm.doc
                },
                freeze: true,
                freeze_message: __("Create Stock Audit..."),
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

    fetch_items: function (frm) {
        if (!frm.doc.warehouse) {
            frappe.msgprint(__("Please select warehouse"));
            return;
        }
        frappe.call({
            method: "jisha_customization.jisha_customization.doctype.jisha_stock_audit_tool.jisha_stock_audit_tool.get_items",
            args: {
                warehouse: frm.doc.warehouse
            },
            callback: function (r) {
                console.log(r.message)
                const requests = r.message || [];

                if (!requests.length) {
                    frappe.msgprint("No Material Requests found for the selected Item Code");
                    return;
                }

                if (frm.doc.items && frm.doc.items.length > 0) {
                    frappe.msgprint("Items already exist in the table. Clear the table to fetch again.");
                    return;
                }

                requests.forEach(d => {
                    frm.add_child("items", {
                        item_code: d.item_code,
                        warehouse_qty: d.actual_qty
                    });
                });

                frm.refresh_field("items");
                frm.save();
            }
        })
    },


    scan_barcode: function (frm) {
        if (frm.doc.scan_barcode) {

            frappe.call({
                method: "jisha_customization.jisha_customization.doctype.jisha_stock_audit_tool.jisha_stock_audit_tool.get_barcode_data",
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
                        let child_data = barcode_data.table_mrql || [];

                        let itemExists = false;
                        let warehouseExists = false;

                        // 1️⃣ Check main barcode_data
                        if (barcode_data.item_code) {
                            itemExists = items.some(d => d.item_code === barcode_data.item_code);
                        }
                        if (barcode_data.warehouse) {
                            warehouseExists = (frm.doc.warehouse === barcode_data.warehouse);
                        }

                        // 2️⃣ Check child_data (if multiple rows in response)
                        if (Array.isArray(child_data) && child_data.length > 0) {
                            child_data.forEach(cd => {
                                if (cd.item_code && !itemExists) {
                                    itemExists = items.some(d => d.item_code === cd.item_code);
                                }
                                if (cd.warehouse && !warehouseExists) {
                                    warehouseExists = (frm.doc.warehouse === cd.warehouse);
                                }
                            });
                        }

                        // 🚨 Validation Rules
                        if (!itemExists) {
                            frappe.msgprint({
                                title: __('Item Mismatch'),
                                indicator: 'red',
                                message: __('Scanned Item Code does not exist in items table.')
                            });
                            frm.set_value("scan_barcode", "");
                            return;
                        }

                        if (!warehouseExists) {
                            frappe.msgprint({
                                title: __('Warehouse Conflict'),
                                indicator: 'red',
                                message: __(
                                    "Scanned Warehouse ({0}) isn't matching with existing warehouse ({1}).",
                                    [barcode_data.warehouse, frm.doc.warehouse]
                                )
                            });
                            frm.set_value("scan_barcode", "");
                            return;
                        }


                        // From Barcode Entry 
                        if (barcode_data.doctype === "Barcode Entry") {
                            let target_item_code = barcode_data.item_code;
                            let scan_qty = barcode_data.qty || 1; // default qty = 1

                            // 🔍 Global Duplicate Check across all rows
                            let duplicateRow = items.find(r => {
                                let existing_barcodes = (r.barcodes || "").split("\n").filter(Boolean);
                                return existing_barcodes.includes(barcode_data.name);
                            });

                            if (duplicateRow) {
                                frappe.msgprint({
                                    title: __('Duplicate Barcode'),
                                    indicator: 'red',
                                    message: __(
                                        "Scanned Barcode already exists in Row #{0} (Item: {1}).",
                                        [duplicateRow.idx, duplicateRow.item_code]
                                    )
                                });
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // 📊 Calculate total quantities across all rows for this item code
                            let total_warehouse_qty = items.filter(d => d.item_code === target_item_code).reduce((sum, d) => sum + (d.warehouse_qty || 0), 0);
                            let total_barcode_qty = items.filter(d => d.item_code === target_item_code).reduce((sum, d) => sum + (d.barcode_qty || 0), 0);
                            let pending_qty = total_warehouse_qty - total_barcode_qty;

                            if (pending_qty <= 0) {
                                frappe.msgprint(`All barcodes for Item ${target_item_code} have already been scanned. No pending quantity left.`);
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            if (scan_qty > pending_qty) {
                                frappe.msgprint(
                                    `Scanned box quantity (${scan_qty}) exceeds pending quantity (${pending_qty}) for Item ${target_item_code}`
                                );
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // 🔍 Find suitable row to update (either the first row that hasn't been scanned yet, or we append a new one)
                            let row = items.find(d => d.item_code === target_item_code && d.warehouse_qty > 0 && !d.barcode_qty);
                            if (!row) {
                                // Add a new child row
                                row = frm.add_child("items", {
                                    item_code: target_item_code,
                                    warehouse_qty: 0,
                                    barcode_qty: 0,
                                    variance_qty: 0
                                });
                            }

                            // ✅ Update row quantities
                            row.barcode_qty = (row.barcode_qty || 0) + scan_qty;
                            row.variance_qty = (row.warehouse_qty || 0) - (row.barcode_qty || 0);

                            // ✅ Append scanned barcode
                            let barcodes = (row.barcodes || "").split("\n").filter(Boolean);
                            barcodes.push(barcode_data.name);
                            row.barcodes = barcodes.join("\n");

                            // ✅ Handle batches
                            let batches = (row.batch || "").split("\n").filter(Boolean);
                            if (barcode_data.batch && !batches.includes(barcode_data.batch)) {
                                batches.push(barcode_data.batch);
                            }
                            frappe.model.set_value(row.doctype, row.name, "batch", batches.join("\n"));

                            frappe.show_alert({
                                message: `Barcode added to Row ${row.idx} (Item: ${row.item_code})`,
                                indicator: 'green'
                            });

                            // ✅ Clear scan field
                            frm.set_value("scan_barcode", "");
                            frm.refresh_field("items");
                            update_batch_valuation_rate(frm, row, function () {
                                frm.save();
                            });
                        }


                        // From Box Creation
                        if (barcode_data.doctype === "Box Creation") {
                            let target_item_code = child_data[0].item_code;
                            let scan_qty = barcode_data.box_qty || 0; // use box_qty for Box Creation

                            // 🔍 Global Duplicate Check across all rows
                            let duplicateBoxRow = null;
                            let duplicateBox = child_data.some(cd => {
                                return items.some(row => {
                                    let existing_boxes = (row.boxes || "").split("\n").filter(Boolean);
                                    let new_boxes = (cd.parent || "").split("\n").filter(Boolean);
                                    let found = row.item_code === cd.item_code &&
                                        new_boxes.some(nb => existing_boxes.includes(nb));
                                    if (found && !duplicateBoxRow) {
                                        duplicateBoxRow = row;
                                    }
                                    return found;
                                });
                            });

                            if (duplicateBox) {
                                frappe.msgprint({
                                    title: __('Duplicate Box'),
                                    indicator: 'red',
                                    message: __(
                                        "Scanned Box already exists in Row #{0} (Item: {1}).",
                                        [duplicateBoxRow ? duplicateBoxRow.idx : '', duplicateBoxRow ? duplicateBoxRow.item_code : '']
                                    )
                                });
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // 📊 Calculate total quantities across all rows for this item code
                            let total_warehouse_qty = items.filter(d => d.item_code === target_item_code).reduce((sum, d) => sum + (d.warehouse_qty || 0), 0);
                            let total_barcode_qty = items.filter(d => d.item_code === target_item_code).reduce((sum, d) => sum + (d.barcode_qty || 0), 0);
                            let pending_qty = total_warehouse_qty - total_barcode_qty;

                            if (pending_qty <= 0) {
                                frappe.msgprint(`All barcodes for Item ${target_item_code} have already been scanned. No pending quantity left.`);
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            if (scan_qty > pending_qty) {
                                frappe.msgprint(
                                    `Scanned box quantity (${scan_qty}) exceeds pending quantity (${pending_qty}) for Item ${target_item_code}`
                                );
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // 🔍 Find suitable row to update (either the first row that hasn't been scanned yet, or we append a new one)
                            let row = items.find(d => d.item_code === target_item_code && d.warehouse_qty > 0 && !d.barcode_qty);
                            if (!row) {
                                // Add a new child row
                                row = frm.add_child("items", {
                                    item_code: target_item_code,
                                    warehouse_qty: 0,
                                    barcode_qty: 0,
                                    variance_qty: 0
                                });
                            }

                            // ✅ Update row quantities
                            row.barcode_qty = (row.barcode_qty || 0) + scan_qty;
                            row.variance_qty = (row.warehouse_qty || 0) - (row.barcode_qty || 0);
                            // row.warehouse_qty = row.variance_qty || 0;

                            // ✅ Append scanned boxes
                            let boxes = (row.boxes || "").split("\n").filter(Boolean);
                            child_data.forEach(cd => {
                                if (!boxes.includes(cd.parent)) {
                                    boxes.push(cd.parent);
                                }
                            });
                            row.boxes = boxes.join("\n");

                            // ✅ Append scanned barcodes from table_mrql
                            let barcodes = (row.barcodes || "").split("\n").filter(Boolean);
                            child_data.forEach(cd => {
                                if (!barcodes.includes(cd.barcode_reference)) {
                                    barcodes.push(cd.barcode_reference);
                                }
                            });
                            row.barcodes = barcodes.join("\n");

                            // ✅ Handle batches
                            let batches = (row.batch || "").split("\n").filter(Boolean);
                            child_data.forEach(cd => {
                                if (cd.batch && !batches.includes(cd.batch)) {
                                    batches.push(cd.batch);
                                }
                            });
                            frappe.model.set_value(row.doctype, row.name, "batch", batches.join("\n"));

                            // ✅ Show alert indicating row updated
                            frappe.show_alert({
                                message: `Box added to Row ${row.idx} (Item: ${row.item_code})`,
                                indicator: 'green'
                            });

                            // ✅ Clear scan field and refresh
                            frm.set_value("scan_barcode", "");
                            frm.refresh_field("items");
                            update_batch_valuation_rate(frm, row, function () {
                                frm.save();
                            });
                        }

                    }


                }
            })

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
    frm.save()
    frappe.show_alert({ message: __("Form cleared successfully"), indicator: "green" });
}


function update_batch_valuation_rate(frm, row, callback) {
    if (row.batch && row.item_code && frm.doc.warehouse) {
        frappe.call({
            method: "jisha_customization.jisha_customization.doctype.jisha_stock_audit_tool.jisha_stock_audit_tool.get_batch_valuation_rate",
            args: {
                item_code: row.item_code,
                warehouse: frm.doc.warehouse,
                batch_no: row.batch
            },
            callback: function (r) {
                if (r.message !== undefined) {
                    frappe.model.set_value(row.doctype, row.name, "batch_valuation_rate", r.message);
                }
                if (callback) callback();
            }
        });
    } else {
        frappe.model.set_value(row.doctype, row.name, "batch_valuation_rate", 0);
        if (callback) callback();
    }
}


frappe.ui.form.on("Jisha Stock Audit Tool Item", {
    batch: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        update_batch_valuation_rate(frm, row);
    }
});

