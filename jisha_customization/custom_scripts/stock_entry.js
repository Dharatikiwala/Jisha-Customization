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

        // Check if any item in frm.doc.items has custom_barcodes_v1 value
        var hasCustomBarcodes = frm.doc.items.some(item => !!item.custom_barcodes_v1);
        if(frm.doc.docstatus === 1 && hasCustomBarcodes) {
            frm.add_custom_button("Create Box", function() {
                frappe.call({
                    method: "jisha_customization.jisha_customization.override.stock_entry.get_items",
                    args: {
                        "doc_name": frm.doc.name
                    },
                    freeze:true,
                    callback: function(r) {
                        if(r.message){
                            // create dialog box where we can add data of r.meesage in child table
                            var fields = [
                                
                                {
                                    fieldtype: "Table",
                                    fieldname: "items_table",
                                    label: "Items",
                                    fields: [
                                        {
                                            fieldtype: "Data",
                                            fieldname: "item_code",
                                            label: "Item Code",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 2
                                        },
                                        {
                                            fieldtype: "Link",
                                            fieldname: "batch_no",
                                            label: "Batch",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Float",
                                            fieldname: "qty",
                                            label: "Qty",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Int",
                                            fieldname: "barcode_qty",
                                            label: "Barcode Qty",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Int",
                                            fieldname: "divide",
                                            label: "Divide",
                                            in_list_view: 1,
                                            columns: 1,
                                            onchange: function () {
                                                const divide = this.get_value();
                                                console.log(divide);
                                                const barcode_qty = this.grid_row.on_grid_fields_dict.barcode_qty.get_value();
                                                if(divide <= 0){
                                                    frappe.msgprint("Divide value must be greater than 0.");
                                                    return;
                                                }

                                                if (divide && barcode_qty) {
                                                    const full_box_val = barcode_qty / divide;
                                                    // Integer part
                                                    const full_box = Math.floor(full_box_val);
                                                    // Fractional part
                                                    const remaining_box = +(full_box_val - full_box).toFixed(5);

                                                    this.grid_row.on_grid_fields_dict.full_box.set_value(full_box);
                                                    this.grid_row.on_grid_fields_dict.remaining_box.set_value(remaining_box);
                                                } else {
                                                    this.grid_row.on_grid_fields_dict.full_box.set_value(0);
                                                    this.grid_row.on_grid_fields_dict.remaining_box.set_value(0);
                                                }
                                            }

                                        },
                                        {
                                            fieldtype: "Int",
                                            fieldname: "full_box",
                                            label: "Full Box",
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Float",
                                            fieldname: "remaining_box",
                                            label: "Remaining Box",
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        // {
                                        //     fieldtype: "small_text",
                                        //     fieldname: "custom_barcodes_v1",
                                        //     label: "Custom Barcodes",
                                        //     in_list_view: 0
                                        // }
                                    ]
                                }
                            ];

                            var dialog = new frappe.ui.Dialog({
                                title: "Items",
                                fields: fields,
                                 size: 'extra-large',
                                primary_action_label: "Create Box",
                                primary_action(values) {
                                    let selected_items = values.items_table.filter(item => item.divide > 0 && item.full_box > 0);
                                    if (selected_items.length === 0) {
                                        frappe.msgprint({
                                            title: __("No Items Selected"),
                                            message: __("Please select at least one item with 'divide' > 0 and 'full_box' > 0."),
                                            indicator: "red"
                                        });
                                        return;
                                    }
                                    frappe.call({
                                        method: "jisha_customization.jisha_customization.override.stock_entry.create_box_creation",
                                        args: {
                                            "item_dict": JSON.stringify(selected_items),
                                            "stock_entry": frm.doc.name,
                                            "date":frm.doc.posting_date
                                        },
                                        freeze:true,
                                        freeze_message: __("Creating Box..."),
                                        callback: function(r) {
                                            console.log(r.message)
                                            if (r.message && r.message.created_items) {
                                                let msg = r.message.created_items.map(item => {
                                                    return `<b>${item.item_code}</b>: ${item.boxes.join(", ")}`;
                                                }).join("<br>");

                                                frappe.msgprint({
                                                    title: __("Box Creation Summary"),
                                                    message: msg,
                                                    indicator: 'green'
                                                });
                                            }
                                        }
                                    });

                                    dialog.hide()
                                }
                            });

                            // Populate child table with data from r.message
                            if (Array.isArray(r.message)) {
                                let table_field = dialog.fields_dict.items_table;

                                // Ensure the table has data array
                                if (!table_field.df.data) {
                                    table_field.df.data = [];
                                }

                                r.message.forEach(function(item) {
                                    table_field.df.data.push({
                                        item_code: item.item_code,
                                        batch_no:item.batch_no,
                                        qty: item.qty,
                                        warehouse:item.t_warehouse,
                                        barcode_qty: item.barcode_count,
                                        custom_barcodes_v1: item.custom_barcodes_v1 || "",
                                    });
                                });

                                table_field.refresh();
                            }

                            dialog.show();


                        }
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

                        if (barcode_data && child_data && child_data.length > 0) {
                            var barcodes = barcode_data.table_mrql.map(function (row) {
                                return row.barcode_reference;
                            }).join("\n");

                            console.log(barcodes);

                            // ----------------------------------------------------------
                            // 1) CHECK IF SAME ITEM+ BATCH ALREADY EXISTS
                            // ----------------------------------------------------------
                            var existingRow = frm.doc.items.find(function (item) {
                                return item.item_code === child_data[0].item_code &&
                                    item.batch_no === child_data[0].batch;
                            });

                            if (existingRow) {
                                // ---------------------------------------
                                // GET ITEM GROUP, JISHA SETTINGS
                                // ---------------------------------------
                                frappe.db.get_value("Item", child_data[0].item_code, "item_group")
                                    .then(item_res => {
                                        const item_group = item_res.message.item_group;

                                        frappe.db.get_doc("Jisha Settings").then(jisha_setting => {
                                            const jisha_group = jisha_setting.item_group;
                                            const jisha_qty = jisha_setting.qty || 1;

                                            frappe.call({
                                                method: "frappe.client.get_list",
                                                args: {
                                                    doctype: "Item Group",
                                                    filters: { parent_item_group: jisha_group },
                                                    fields: ["name"]
                                                },
                                                callback: (r) => {
                                                    const sub_groups = r.message.map(g => g.name);
                                                    const valid_group =
                                                        (item_group === jisha_group) ||
                                                        sub_groups.includes(item_group);

                                                    // -------------------------------------
                                                    // CORRECT QTY ACCUMULATION
                                                    // -------------------------------------
                                                    let add_qty = valid_group
                                                        ? barcode_data.box_qty / jisha_qty
                                                        : barcode_data.box_qty;

                                                    existingRow.qty += add_qty;

                                                    // -------------------------------------
                                                    // MERGE BARCODES
                                                    // -------------------------------------
                                                    let existingBarcodes = existingRow.custom_barcodes_v1
                                                        ? existingRow.custom_barcodes_v1.split("\n")
                                                        : [];

                                                    barcode_data.table_mrql.forEach(function (row) {
                                                        if (!existingBarcodes.includes(row.barcode_reference)) {
                                                            existingBarcodes.push(row.barcode_reference);
                                                        }
                                                    });

                                                    existingRow.custom_barcodes_v1 = existingBarcodes.join("\n");

                                                    // -------------------------------------
                                                    // MERGE custom_box_reference
                                                    // -------------------------------------
                                                    let existingRefs = existingRow.custom_box_reference
                                                        ? existingRow.custom_box_reference.split("\n")
                                                        : [];

                                                    if (!existingRefs.includes(barcode_data.name)) {
                                                        existingRefs.push(barcode_data.name);
                                                    }

                                                    existingRow.custom_box_reference = existingRefs.join("\n");

                                                    frm.refresh_field("items");
                                                    frm.set_value("custom_scan_barcodes", "");
                                                    frm.save();
                                                }
                                            });
                                        });
                                    });

                                return;
                            }

                            // ----------------------------------------------------------
                            // 2) IF NO EXISTING ROW → CREATE NEW ROW
                            // ----------------------------------------------------------
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

                            const first_item_code = child_data[0].item_code;

                            // Step 1: Get Item Group of scanned item
                            frappe.db.get_value("Item", first_item_code, "item_group")
                                .then(item_res => {
                                    const item_group = item_res.message.item_group;

                                    // Step 2: Get Jisha Setting
                                    frappe.db.get_doc("Jisha Settings").then(jisha_setting => {
                                        const jisha_group = jisha_setting.item_group;
                                        const jisha_qty = jisha_setting.qty || 1;

                                        // Step 3: Get Jisha sub-groups
                                        frappe.call({
                                            method: "frappe.client.get_list",
                                            args: {
                                                doctype: "Item Group",
                                                filters: { parent_item_group: jisha_group },
                                                fields: ["name"]
                                            },
                                            callback: (r) => {
                                                const sub_groups = r.message.map(g => g.name);
                                                const valid_group =
                                                    (item_group === jisha_group) ||
                                                    sub_groups.includes(item_group);

                                                // -----------------------------------------
                                                // NEW ROW ASSIGNMENT
                                                // -----------------------------------------
                                                row.item_code = first_item_code;
                                                row.s_warehouse = child_data[0].warehouse;
                                                row.batch_no = child_data[0].batch;

                                                // First scan, single reference
                                                row.custom_box_reference = barcode_data.name;

                                                row.custom_barcodes_v1 = barcodes;
                                                row.use_serial_batch_fields = 1;

                                                // -----------------------------------------
                                                // NEW ROW QTY CALCULATION
                                                // -----------------------------------------
                                                if (valid_group) {
                                                    row.qty = barcode_data.box_qty / jisha_qty;
                                                } else {
                                                    row.qty = barcode_data.box_qty;
                                                }

                                                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                                                frm.refresh_field("items");
                                                frm.set_value("custom_scan_barcodes", "");
                                                frm.save();
                                            }
                                        });
                                    });
                                });
                        }

                        else {
                            // Keep your else block unchanged as per your instruction
                            var barcodeExistsIndex = frm.doc.items.findIndex(function(item) {
                                var barcodesArray = item.custom_barcodes_v1 ? item.custom_barcodes_v1.split("\n") : [];
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
                                existingRow.custom_barcodes_v1 += `\n${barcode_data.name}`;
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
                                row.custom_barcodes_v1 = barcode_data.name;
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