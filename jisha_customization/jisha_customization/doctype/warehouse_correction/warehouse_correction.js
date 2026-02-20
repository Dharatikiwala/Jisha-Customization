// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt


// frappe.ui.form.on("Warehouse Correction", {
//     refresh(frm) {

//         if (!frm.doc.enable) return;

//         // ✅ Check if there are unprocessed rows
//         const has_unprocessed = (frm.doc.items || []).some(d => d.is_processed);

//         if (has_unprocessed) {
//             frm.dashboard.set_headline_alert(
//                 __("All rows are already processed."),
//                 "green"
//             );
//             return;
//         }

//         frm.add_custom_button(__("Apply Warehouse Correction"), () => {

//             frappe.confirm(
//                 __(
//                     "This action will update warehouse values based on row Type.<br><br>" +
//                     "<b>This operation cannot be undone.</b><br><br>" +
//                     "Do you want to continue?"
//                 ),
//                 () => {

//                     frappe.call({
//                         method:
//                             "jisha_customization.jisha_customization.doctype.warehouse_correction.warehouse_correction.run_warehouse_correction",
//                         args: {
//                             docname: frm.doc.name,
//                         },
//                         freeze: true,
//                         freeze_message: __("Applying warehouse correction..."),
//                         callback: function (r) {
//                             if (!r.exc) {
//                                 frappe.msgprint({
//                                     title: __("Success"),
//                                     message: r.message.message,
//                                     indicator: "green",
//                                 });
//                                 frm.reload_doc();
//                             }
//                         },
//                     });

//                 },
//                 () => {
//                     frappe.show_alert({
//                         message: __("Warehouse correction cancelled"),
//                         indicator: "orange",
//                     });
//                 }
//             );

//         }).addClass("btn-primary");

//         frm.add_custom_button("Clear", () => {
//             frm.clear_table("items");
//             frm.refresh_field("items");
//             frm.dirty();
//             frm.save()
//         }).addClass("btn-danger");
//     },
// });


frappe.ui.form.on("Warehouse Correction", {
    refresh(frm) {

        if (!frm.doc.enable) return;

        const has_unprocessed = (frm.doc.items || []).some(d => !d.is_processed);

        if (has_unprocessed) {

            // ✅ Apply Button
            frm.add_custom_button(__("Apply Warehouse Correction"), () => {

                frappe.confirm(
                    __("This action will update warehouse values.<br><br><b>This operation cannot be undone.</b><br><br>Do you want to continue?"),
                    () => {

                        frappe.call({
                            method: "jisha_customization.jisha_customization.doctype.warehouse_correction.warehouse_correction.run_warehouse_correction",
                            args: { docname: frm.doc.name },
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
                            }
                        });

                    }
                );

            }).addClass("btn-primary");

        }
        frm.add_custom_button(__("Clear"), () => {

            frappe.confirm(
                __("This will remove ALL rows including processed ones. Continue?"),
                () => {

                    frm.set_value("items", []);
                    frm.refresh_field("items");
                    frm.dirty();
                    frm.save();

                    frappe.show_alert({
                        message: __("All rows cleared."),
                        indicator: "red"
                    });
                }
            );

        }).addClass("btn-danger");
    }
});