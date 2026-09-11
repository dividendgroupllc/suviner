# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""ERPNext yadro-bug workaround (2026-09-11).

Desk'da yangi Sales Invoice'da mijoz tanlanganda ERPNext
`sales_invoice.get_loyalty_programs`ni chaqiradi; u ichkarida Loyalty
Program'ni `"ifnull(to_date, ...)"` filtri bilan so'raydi. Frappe db_query
bu ifodadagi `to_date`ni backtick'lamaydi, MariaDB 11.5+/12.x esa TO_DATE'ni
zaxira funksiya nomi deb biladi → jadval BO'SH bo'lsa ham 1064 sintaksis
xatosi. Bu override aynan o'sha semantikani xavfsiz SQL bilan takrorlaydi
(hooks.py: override_whitelisted_methods).
"""

import frappe
from frappe.utils import today


@frappe.whitelist()
def get_loyalty_programs(customer):
	"""erpnext...sales_invoice.get_loyalty_programs bilan bir xil xulq:
	mijozga mos programni o'rnatadi yoki mos programlar ro'yxatini qaytaradi."""
	customer_doc = frappe.get_doc("Customer", customer)
	if customer_doc.loyalty_program:
		return [customer_doc.loyalty_program]

	lp_details = _applicable_loyalty_programs(customer_doc)

	if len(lp_details) == 1:
		customer_doc.db_set("loyalty_program", lp_details[0])
	return lp_details


def _applicable_loyalty_programs(doc):
	"""customer.py::get_loyalty_programs nusxasi — faqat so'rov tuzatilgan:
	`to_date`/`from_date` backtick ichida, filtr semantikasi aynan yadrodagidek
	(from_date <= bugun, coalesce(to_date, '2500-01-01') >= bugun)."""
	from erpnext.selling.doctype.customer.customer import get_nested_links

	loyalty_programs = frappe.db.sql(
		"""
		select name, customer_group, customer_territory
		from `tabLoyalty Program`
		where auto_opt_in = 1
		  and `from_date` <= %(today)s
		  and coalesce(`to_date`, '2500-01-01') >= %(today)s
		""",
		{"today": today()},
		as_dict=True,
	)

	lp_details = []
	for loyalty_program in loyalty_programs:
		if (
			not loyalty_program.customer_group
			or doc.customer_group
			in get_nested_links(
				"Customer Group", loyalty_program.customer_group, doc.flags.ignore_permissions
			)
		) and (
			not loyalty_program.customer_territory
			or doc.territory
			in get_nested_links("Territory", loyalty_program.customer_territory, doc.flags.ignore_permissions)
		):
			lp_details.append(loyalty_program.name)

	return lp_details
