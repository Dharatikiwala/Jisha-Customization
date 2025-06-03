// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Jisha Settings", {
	refresh(frm) {
        frm.set_query('item_group', () => {
            return {
                filters: {
                    is_group: 1
                }
            }
        })
	},
});
