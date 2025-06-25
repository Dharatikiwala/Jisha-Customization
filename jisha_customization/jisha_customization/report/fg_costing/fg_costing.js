// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.query_reports["FG Costing"] = {
	"filters": [
		{
			fieldname: "from_date",
			reqd: 1,
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(frappe.datetime.get_today()),
		},
		{
			fieldname: "to_date",
			reqd: 1,
			default: frappe.datetime.month_end(frappe.datetime.get_today()),
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname:"item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					filters: {
						"disabled": 0
					}
				};
			}
		},
		{
			fieldname:"item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group"
		},
		{
			fieldname:"warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: function() {
				return {
					filters: {
						"is_group": 1
					}
				};
			}
		}
	]
};
