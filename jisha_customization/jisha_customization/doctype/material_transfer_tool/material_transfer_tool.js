// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Transfer Tool", {
	refresh(frm) {
        frm.add_custom_button("Create Material Transfer", function () {
            frappe.call({
                method: "jisha_customization.jisha_customization.doctype.material_transfer_tool.material_transfer_tool.create_mt",
                args: {
                    "items": frm.doc.items
                },
                freeze: true,
                freeze_message: __("Creating Material Transfer..."),
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

        frm.add_custom_button(__('Clear Form'), function() {
            clear_all_fields(frm);
        });

	},

    fetch_material_request: function(frm) {
        if (!frm.doc.item_code) {
            frappe.throw("Please select Item Code");
        }

        frappe.call({
            method: "jisha_customization.jisha_customization.doctype.material_transfer_tool.material_transfer_tool.get_material_requests",
            args: { item_code: frm.doc.item_code },
            freeze:true,
            callback: function(r) {
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
                        material_request: d.material_request,
                        mr_qty: d.qty,
                        mr_date: d.transaction_date,
                        target_warehouse: d.warehouse,
                        material_request_item: d.material_request_item,
                        branch:d.branch
                    });
                });

                frm.refresh_field("items");
                frm.save();
            }
        });
    },

    scan_barcode: function(frm) {
        if (frm.doc.scan_barcode) {
            frappe.call({
                method: "jisha_customization.jisha_customization.doctype.material_transfer_tool.material_transfer_tool.get_barcode_data",
                args: {
                    "barcode_data": frm.doc.scan_barcode
                },
                freeze:true,
                callback: function(res) {
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
                        console.log(barcode_data);
                        console.log(child_data);

                        let itemExists = false;
                        let warehouseExists = false;

                        // 1️⃣ Check main barcode_data
                        if (barcode_data.item_code) {
                            itemExists = items.some(d => d.item_code === barcode_data.item_code);
                        }
                        if (barcode_data.warehouse) {
                            warehouseExists = items.some(d => d.target_warehouse === barcode_data.warehouse);
                        }

                        // 2️⃣ Check child_data (if multiple rows in response)
                        if (Array.isArray(child_data) && child_data.length > 0) {
                            child_data.forEach(cd => {
                                if (cd.item_code && !itemExists) {
                                    itemExists = items.some(d => d.item_code === cd.item_code);
                                }
                                if (cd.warehouse && !warehouseExists) {
                                    warehouseExists = items.some(d => d.target_warehouse === cd.warehouse);
                                }
                            });
                        }

                        console.log(itemExists)

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

                        if (warehouseExists) {
                            frappe.msgprint({
                                title: __('Warehouse Conflict'),
                                indicator: 'red',
                                message: __('Scanned Warehouse already exists in items table.')
                            });
                            frm.set_value("scan_barcode", "");
                            return;
                        }

                        // From Barcode Entry 
                        if (barcode_data.doctype === "Barcode Entry") {
                            // 🔍 Check for duplicate barcode
                            let duplicateInfo = null;

                            items.forEach((row, idx) => {
                                let existing_barcodes = (row.barcodes || "").split("\n").filter(Boolean);
                                if (
                                    row.item_code === barcode_data.item_code &&
                                    row.batch === barcode_data.batch &&
                                    existing_barcodes.includes(barcode_data.name)
                                ) {
                                    duplicateInfo = {
                                        row: idx + 1,
                                        item_code: row.item_code,
                                        batch: row.batch
                                    };
                                }
                            });

                            if (duplicateInfo) {
                                frappe.msgprint({
                                    title: __('Duplicate Barcode'),
                                    indicator: 'red',
                                    message: __(
                                        "Scanned Barcode already exists in Row #{0} (Item: {1}, Batch: {2}).",
                                        [duplicateInfo.row, duplicateInfo.item_code, duplicateInfo.batch]
                                    )
                                });
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // ✅ Find the first row for this item with pending qty > 0
                            let row = items.find(d =>
                                d.item_code === barcode_data.item_code &&
                                d.warehouse !== barcode_data.warehouse &&
                                ((d.mr_qty || 0) > (d.barcode_qty || 0)) // only if pending > 0
                            );

                            if (row) {
                                let scan_qty = barcode_data.qty || 1; // fallback to 1 if qty missing
                                let pending_qty = (row.mr_qty || 0) - (row.barcode_qty || 0);

                                if (scan_qty > pending_qty) {
                                    frappe.msgprint(
                                        `Scanned box quantity (${scan_qty}) exceeds pending quantity (${pending_qty}) for Item ${row.item_code} (Row ${row.idx})`
                                    );
                                    frm.set_value("scan_barcode", "");
                                    return;
                                }

                                // ✅ Update row quantities
                                row.barcode_qty = (row.barcode_qty || 0) + scan_qty;
                                row.pending_qty = (row.mr_qty || 0) - (row.barcode_qty || 0);

                                // ✅ Append scanned barcode reference
                                let barcodes = (row.barcodes || "").split("\n").filter(Boolean);
                                if (!barcodes.includes(barcode_data.name)) {
                                    barcodes.push(barcode_data.name);
                                }
                                row.barcodes = barcodes.join("\n");

                                // ✅ Update batch & warehouse
                                row.batch = barcode_data.batch;
                                row.source_warehouse = barcode_data.warehouse;
                            } else {
                                frappe.msgprint({
                                    title: __('No Pending Row Found'),
                                    indicator: 'orange',
                                    message: __(
                                        "All rows for Item {0} are fully scanned. No pending quantities left.",
                                        [barcode_data.item_code]
                                    )
                                });
                            }

                            
                        }

                        // if(barcode_data.doctype === "Box Creation"){

                        //     // 👉 Duplicate check
                        //     let duplicateBox = child_data.some(cd => {
                        //         return items.some(row => {
                        //             let existing_boxes = (row.boxes || "").split("\n").filter(Boolean);
                        //             return row.item_code === cd.item_code &&
                        //                 (row.batch_no || row.batch) === cd.batch &&
                        //                 existing_boxes.includes(cd.parent);
                        //         });
                        //     });

                        //     if (duplicateBox) {
                        //         frappe.msgprint('Scanned box already exists in items.');
                        //         frm.set_value("scan_barcode", "");
                        //         return;
                        //     }

                        //     let scan_qty = barcode_data.box_qty || 1;
                        //     let validationError = child_data.find(cd => {
                        //         let row = items.find(d => d.item_code === cd.item_code);
                        //         let pending_qty = (row?.mr_qty || 0) - (row?.barcode_qty || 0);
                        //         return scan_qty > pending_qty;
                        //     });

                        //     if (validationError) {
                        //         let row = items.find(d => d.item_code === validationError.item_code);
                        //         frappe.msgprint(`Scanned box quantity (${scan_qty}) exceeds pending quantity (${(row?.mr_qty || 0) - (row?.barcode_qty || 0)}) for item ${row.item_code} row ${row.idx}`);
                        //         frm.set_value("scan_barcode", "");
                        //         return;
                        //     }


                        //     // 👉 Update rows
                        //     child_data.forEach(cd => {
                        //         let row = items.find(d => d.item_code === cd.item_code && d.warehouse !== cd.warehouse);
                        //         if (row) {
                        //             row.barcode_qty = (row.barcode_qty || 0) + 1;
                        //             row.pending_qty = (row.mr_qty || 0) - (row.barcode_qty || 0);
                        //             row.batch = cd.batch;
                        //             row.source_warehouse = cd.warehouse;

                        //             // merge unique barcodes
                        //             let existing_barcodes = (row.barcodes || "").split("\n").filter(Boolean);
                        //             if (!existing_barcodes.includes(cd.barcode_reference)) {
                        //                 existing_barcodes.push(cd.barcode_reference);
                        //             }
                        //             row.barcodes = existing_barcodes.join("\n");

                        //             // merge unique boxes
                        //             let existing_boxes = (row.boxes || "").split("\n").filter(Boolean);
                        //             if (!existing_boxes.includes(cd.parent)) {
                        //                 existing_boxes.push(cd.parent);
                        //             }
                        //             row.boxes = existing_boxes.join("\n");
                        //         }
                        //     });
                        // }

                        // if (barcode_data.doctype === "Box Creation") {

                        //     let scan_qty = barcode_data.box_qty || 1;

                        //     // Duplicate check for boxes
                        //     let duplicateBox = child_data.some(cd => {
                        //         return items.some(row => {
                        //             let existing_boxes = (row.boxes || "").split("\n").filter(Boolean);
                        //             let new_boxes = (cd.parent || "").split("\n").filter(Boolean);
                        //             return row.item_code === cd.item_code &&
                        //                 (row.batch_no || row.batch) === cd.batch &&
                        //                 new_boxes.some(nb => existing_boxes.includes(nb));
                        //         });
                        //     });

                        //     if (duplicateBox) {
                        //         frappe.msgprint('Scanned box already exists in items.');
                        //         frm.set_value("scan_barcode", "");
                        //         return;
                        //     }

                        //     // Validation: warn if scanned qty > pending
                        //     let validationError = child_data.find(cd => {
                        //         let row = items.find(d => d.item_code === cd.item_code);
                        //         let pending = (row?.mr_qty || 0) - (row?.barcode_qty || 0);
                        //         return row && row.barcode_qty !== row.mr_qty && pending > 0 && scan_qty > pending;
                        //     });

                        //     if (validationError) {
                        //         let row = items.find(d => d.item_code === validationError.item_code);
                        //         frappe.throw(
                        //             `Scanned box quantity (${scan_qty}) exceeds pending quantity (${(row?.mr_qty || 0) - (row?.barcode_qty || 0)}) for item ${row.item_code} row ${row.idx}`
                        //         );
                        //     }

                        //     // Find first eligible row
                        //     let targetRow = null;

                        //     for (let cd of child_data) {
                        //         let row = items.find(d => 
                        //             d.item_code === cd.item_code && 
                        //             d.barcode_qty !== d.mr_qty && 
                        //             ((d.mr_qty || 0) - (d.barcode_qty || 0)) > 0
                        //         );
                        //         if (row) {
                        //             targetRow = row;
                        //             break; // stop at first eligible row
                        //         }
                        //     }

                        //     if (!targetRow) {
                        //         frappe.msgprint("No eligible row found for this scanned box.");
                        //         frm.set_value("scan_barcode", "");
                        //         return;
                        //     }

                        //     // Update qtys for the target row
                        //     let pending = (targetRow.mr_qty || 0) - (targetRow.barcode_qty || 0);
                        //     targetRow.barcode_qty += scan_qty;
                        //     targetRow.pending_qty = pending - scan_qty;

                        //     // Get first child for batch & warehouse info
                        //     let firstChild = child_data.find(cd => cd.item_code === targetRow.item_code);
                        //     if (firstChild) {
                        //         targetRow.batch = firstChild.batch;
                        //         targetRow.source_warehouse = firstChild.warehouse;
                        //     }

                        //     // Merge all barcodes for this row
                        //     let existing_barcodes = (targetRow.barcodes || "").split("\n").filter(Boolean);
                        //     child_data.filter(cd => cd.item_code === targetRow.item_code).forEach(cd => {
                        //         let new_barcodes = (cd.barcode_reference || "").split("\n").filter(Boolean);
                        //         existing_barcodes.push(...new_barcodes);
                        //     });
                        //     targetRow.barcodes = Array.from(new Set(existing_barcodes)).join("\n");

                        //     // Merge all boxes for this row
                        //     let existing_boxes = (targetRow.boxes || "").split("\n").filter(Boolean);
                        //     child_data.filter(cd => cd.item_code === targetRow.item_code).forEach(cd => {
                        //         let new_boxes = (cd.parent || "").split("\n").filter(Boolean);
                        //         existing_boxes.push(...new_boxes);
                        //     });
                        //     targetRow.boxes = Array.from(new Set(existing_boxes)).join("\n");

                        //     // Refresh form
                        //     frm.refresh_field("items");
                        //     frm.set_value("scan_barcode", "");
                        // }


                        if (barcode_data.doctype === "Box Creation") {

                            let scan_qty = barcode_data.box_qty || 1;

                            // Duplicate check for boxes
                            let duplicateBox = child_data.some(cd => {
                                return items.some(row => {
                                    let existing_boxes = (row.boxes || "").split("\n").filter(Boolean);
                                    let new_boxes = (cd.parent || "").split("\n").filter(Boolean);
                                    return row.item_code === cd.item_code &&
                                        (row.batch_no || row.batch) === cd.batch &&
                                        new_boxes.some(nb => existing_boxes.includes(nb));
                                });
                            });

                            if (duplicateBox) {
                                frappe.msgprint('Scanned box already exists in items.');
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // Find first eligible row
                            let targetRow = null;
                            for (let cd of child_data) {
                                let row = items.find(d => 
                                    d.item_code === cd.item_code && 
                                    d.barcode_qty !== d.mr_qty && 
                                    ((d.mr_qty || 0) - (d.barcode_qty || 0)) > 0
                                );
                                if (row) {
                                    targetRow = row;
                                    break; // stop at first eligible row
                                }
                            }

                            if (!targetRow) {
                                frappe.msgprint("No eligible row found for this scanned box.");
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // Validation: total scanned qty must not exceed pending
                            let pending_qty = (targetRow.mr_qty || 0) - (targetRow.barcode_qty || 0);
                            let total_scan_qty = child_data
                                .filter(cd => cd.item_code === targetRow.item_code)
                                .reduce((sum, cd) => sum + (cd.box_qty || 1), 0);

                            if (total_scan_qty > pending_qty) {
                                frappe.msgprint(
                                    `Scanned total box quantity <b>(${total_scan_qty})</b> exceeds pending quantity <b>(${pending_qty})</b> for item <b>${targetRow.item_code}</b> row <b>${targetRow.idx}</b>`
                                );
                                frm.set_value("scan_barcode", "");
                                return;
                            }

                            // Update qtys
                            targetRow.barcode_qty += scan_qty;
                            targetRow.pending_qty = pending_qty - scan_qty;

                            // Get first child for batch & warehouse info
                            let firstChild = child_data.find(cd => cd.item_code === targetRow.item_code);
                            if (firstChild) {
                                targetRow.batch = firstChild.batch;
                                targetRow.source_warehouse = firstChild.warehouse;
                            }

                            // Merge all barcodes for this row
                            let existing_barcodes = (targetRow.barcodes || "").split("\n").filter(Boolean);
                            child_data.filter(cd => cd.item_code === targetRow.item_code).forEach(cd => {
                                let new_barcodes = (cd.barcode_reference || "").split("\n").filter(Boolean);
                                existing_barcodes.push(...new_barcodes);
                            });
                            targetRow.barcodes = Array.from(new Set(existing_barcodes)).join("\n");

                            // Merge all boxes for this row
                            let existing_boxes = (targetRow.boxes || "").split("\n").filter(Boolean);
                            child_data.filter(cd => cd.item_code === targetRow.item_code).forEach(cd => {
                                let new_boxes = (cd.parent || "").split("\n").filter(Boolean);
                                existing_boxes.push(...new_boxes);
                            });
                            targetRow.boxes = Array.from(new Set(existing_boxes)).join("\n");

                            // Refresh form
                            frm.refresh_field("items");
                            frm.set_value("scan_barcode", "");
                        }




                        frm.refresh_field("items");
                        frm.set_value("scan_barcode", "");
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
    $.each(frm.fields_dict, function(fieldname, field) {
        if (field.df.fieldtype !== "Button" && 
            field.df.fieldtype !== "Section Break" && 
            field.df.fieldtype !== "Column Break" && 
            field.df.fieldtype !== "HTML") {
            frm.set_value(fieldname, null);
        }
    });

    frm.refresh_fields();
    frm.save()
    frappe.show_alert({message: __("Form cleared successfully"), indicator: "green"});
}