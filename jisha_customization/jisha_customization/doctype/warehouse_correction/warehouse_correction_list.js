// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.listview_settings["Warehouse Correction"] = {
	onload(listview) {
		// Block delete triggered via list view bulk actions
		listview.delete_document = function (...args) {
			frappe.throw(__("Warehouse Correction records cannot be deleted."));
		};
	},
};
