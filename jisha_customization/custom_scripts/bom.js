frappe.ui.form.on('BOM', {
	refresh(frm) {
        frm.set_query('expense_account', 'custom_additonal_costs', () => {
            return {
                filters: {
                    company: frm.doc.company,
                    account_type: ["in", ["Tax","Chargeable","Income Account","Expenses Included In Valuation","Expenses Included In Asset Valuation"]]
                }
            }
        })
    }

})