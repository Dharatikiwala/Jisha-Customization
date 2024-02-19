frappe.ui.form.on('Work Order', {
	refresh(frm) {
		frm.add_custom_button("Get Item From", function () {
            frappe.prompt([
                {
                    label: __("Machine"),
                    fieldname: "jisha_processing_machine",
                    fieldtype: "Link",
                    options: "Jisha Processing Machine",
                    get_query: function () {
                        return {
                            filters: {
                                is_active: 1
                            }
                        };
                    }
                }
            ],
            function (values) {
                if (values.jisha_processing_machine) {
                    frappe.db.get_doc('Jisha Processing Machine', values.jisha_processing_machine)
                    .then(doc => {
                        doc.items.forEach(item => {
                            var newrow = frappe.model.add_child(frm.doc, "Work Order Item", "required_items");
                            newrow.item_code = item.item;
                            newrow.required_qty = item.qty;
                            refresh_field("required_items");
                            frm.script_manager.trigger("item_code", newrow.doctype, newrow.name);
                        });
        
                        frm.save();
                    })
                
                } 
                else {
                    frappe.msgprint("Please select a Jisha Processing Machine");
                }
            },
            __("Select Jisha Processing Machine"),
            __("Set Data")
            );
        });
        
	},

})