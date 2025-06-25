# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from jisha_customization.jisha_customization.report.jisha_sales_analytics.jisha_sales_analytics import JishaAnalytics


def execute(filters=None):
	return JishaAnalytics(filters).run()
