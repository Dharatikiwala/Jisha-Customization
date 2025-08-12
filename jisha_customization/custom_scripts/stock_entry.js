frappe.ui.form.on('Stock Entry', {
    refresh(frm) {
        if(frm.doc.docstatus === 1 && (frm.doc.purpose === "Manufacture" || frm.doc.purpose === "Material Receipt")) {
            frm.add_custom_button("Generate Barcode Entry", function() {
                frappe.call({
                    method: "jisha_customization.jisha_customization.override.stock_entry.create_barcode_entry",
                    args: {
                        "doc": frm.doc
                    },
                    freeze:true,
                    freeze_message: __("Generating Barcode Entry..."),
                    callback: function(r) {
                        console.log(r.message);
                        frm.reload_doc()
                    }
                });
            });
        }
    },

    custom_scan_barcodes: function(frm) {
        if (frm.doc.custom_scan_barcodes) {
            frappe.call({
                method: 'jisha_customization.jisha_customization.override.sales_invoice.get_barcode_data',
                args: {
                    "barcode_data": frm.doc.custom_scan_barcodes
                },
                callback: function(response) {
                    if (response && response.message) {
                        var barcode_data = response.message;

                        if (barcode_data.status === 'error') {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: barcode_data.message
                            });
                            frm.set_value("custom_scan_barcodes", "");
                            return;
                        }

                        var child_data = barcode_data.table_mrql;
                        console.log(barcode_data);

                        // ✅ Only this block is changed
                        if (barcode_data && child_data && child_data.length > 0) {
                            var barcodes = barcode_data.table_mrql.map(function(row) {
                                return row.barcode_reference;
                            }).join("\n");
                            console.log(barcodes);

                            // Check if item_code and batch_no already exist in any row
                            var existingRow = frm.doc.items.find(function(item) {
                                return item.item_code === child_data[0].item_code &&
                                    item.batch_no === child_data[0].batch;
                            });

                            if (existingRow) {
                                // ✅ Add box_qty
                                existingRow.qty += parseFloat(barcode_data.box_qty) || 1;

                                // ✅ Append barcodes only if not already in the list
                                let existingBarcodes = existingRow.custom_barcodes
                                    ? existingRow.custom_barcodes.split("\n")
                                    : [];

                                barcode_data.table_mrql.forEach(function(row) {
                                    if (!existingBarcodes.includes(row.barcode_reference)) {
                                        existingBarcodes.push(row.barcode_reference);
                                    }
                                });

                                existingRow.custom_barcodes = existingBarcodes.join("\n");
                                frm.refresh_field("items");
                                frm.set_value("custom_scan_barcodes", "");
                                frm.save();
                                return;
                            }

                            // 🔽 If no matching row, proceed to add new row
                            var barcodeExists = frm.doc.items.some(function(item) {
                                return item.custom_barcodes === barcodes;
                            });

                            if (barcodeExists) {
                                frappe.msgprint('The scanned box barcode already exists in the items table.');
                                frm.set_value("custom_scan_barcodes", "");
                                return;
                            } else {
                                let row;
                                const emptyRow = frm.doc.items.find(item =>
                                    (item.qty === 0 || !item.qty) ||
                                    !item.item_code
                                );

                                if (emptyRow) {
                                    row = emptyRow;
                                } else {
                                    row = frappe.model.add_child(frm.doc, "Stock Entry Detail", "items");
                                }

                                row.item_code = child_data[0].item_code;
                                row.s_warehouse = child_data[0].warehouse;
                                row.batch_no = child_data[0].batch;
                                row.qty = barcode_data.box_qty;
                                row.custom_box_creation_reference = barcode_data.name;
                                row.custom_barcodes = barcodes;
                                row.use_serial_batch_fields = 1;

                                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                                frm.refresh_field("items");
                                frm.set_value("custom_scan_barcodes", "");
                                frm.save();
                            }
                        } 
                        else {
                            // Keep your else block unchanged as per your instruction
                            var barcodeExistsIndex = frm.doc.items.findIndex(function(item) {
                                var barcodesArray = item.custom_barcodes ? item.custom_barcodes.split("\n") : [];
                                return barcodesArray.includes(barcode_data.name);
                            });
                            if (barcodeExistsIndex !== -1) {
                                frappe.msgprint(`The scanned barcode already exists in the items table at row ${barcodeExistsIndex + 1}.`);
                                frm.set_value("custom_scan_barcodes", "");
                                return;
                            }

                            var existingRow = frm.doc.items.find(function(item) {
                                return item.item_code === barcode_data.item_code && item.batch_no === barcode_data.batch;
                            });

                            if (existingRow) {
                                existingRow.qty += 1;
                                existingRow.custom_barcodes += `\n${barcode_data.name}`;
                                frm.refresh_field("items");
                            } else {
                                let row;
                                const emptyRow = frm.doc.items.find(item =>
                                    (item.qty === 0 || !item.qty) ||
                                    !item.item_code
                                );

                                if (emptyRow) {
                                    row = emptyRow;
                                } else {
                                    row = frappe.model.add_child(frm.doc, "Stock Entry Detail", "items");
                                }

                                row.item_code = barcode_data.item_code;
                                row.s_warehouse = barcode_data.warehouse;
                                row.batch_no = barcode_data.batch;
                                row.qty = parseFloat(barcode_data.item_qty);
                                row.custom_barcodes = barcode_data.name;
                                row.use_serial_batch_fields = 1;

                                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                                frm.refresh_field("items");
                            }

                            frm.set_value("custom_scan_barcodes", "");
                            frm.save();
                        }
                    }
                }
            });
        }
    }

});