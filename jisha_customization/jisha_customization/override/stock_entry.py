import frappe

def before_save(self,method):
    entry_type = frappe.db.get_value("Stock Entry Type", self.stock_entry_type,"purpose")

    if not entry_type:
        return

    if entry_type == "Manufacture" and self.from_bom == 1 and self.bom_no:
        calculate_additional_cost(self)

def calculate_additional_cost(self):
    bom_details = frappe.get_doc("BOM", self.bom_no)
    
    if not bom_details.custom_additonal_costs:
        return
        
    self.additional_costs = []
    for ac in bom_details.custom_additonal_costs:
        if ac.amount:
            self.append("additional_costs", {
                "expense_account": ac.expense_account,
                "description": ac.description,
                "amount": ac.amount * self.fg_completed_qty
            })
    
    self.total_additional_costs = sum(t.amount for t in self.get("additional_costs"))
