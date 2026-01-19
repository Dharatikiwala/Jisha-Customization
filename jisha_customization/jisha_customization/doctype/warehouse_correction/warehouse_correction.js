// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Correction", {
	refresh(frm) {
		if (frm.doc.enable) {
			frm.add_custom_button(__("Apply Warehouse Correction"), () => {
                frappe.confirm(
                    __(
                        "This action will update <b>Barcode Entry</b> and " +
                            "<b>Box Creation</b> warehouse values.<br><br>" +
                            "<b>This operation cannot be undone.</b><br><br>" +
                            "Do you want to continue?",
                    ),
                    () => {
                        // YES
                        frappe.call({
                            method:
                                "jisha_customization.jisha_customization.doctype.warehouse_correction.warehouse_correction.run_warehouse_correction",
                            args: {
                                docname: frm.doc.name,
                            },
                            freeze: true,
                            freeze_message: __("Applying warehouse correction..."),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.msgprint({
                                        title: __("Success"),
                                        message: r.message.message,
                                        indicator: "green",
                                    });
                                    frm.reload_doc();
                                }
                            },
                        });
                    },
                    () => {
                        // NO
                        frappe.show_alert({
                            message: __("Warehouse correction cancelled"),
                            indicator: "orange",
                        });
                    },
                );
			}).addClass("btn-primary");

            frm.add_custom_button("Clear", () => {
                frm.set_value("is_applied", 0);
                frm.clear_table("items");
                frm.refresh_field("items");
                frm.save()
            }).addClass("btn-danger");
		}
	},
});
