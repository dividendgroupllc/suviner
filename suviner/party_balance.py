# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Kontragent (Customer/Supplier/Employee/Shareholder/...) joriy qoldig'i.

Sales Invoice, Purchase Invoice, Journal Entry va Kassa formalarida kontragent
tanlanganda uning GL bo'yicha qoldig'ini ko'rsatish uchun bitta umumiy endpoint.

Ishora qoidasi (GL: debit − kredit, kompaniya valyutasida):
  balance > 0  → kontragent BIZGA qarzdor (debitor)
  balance < 0  → BIZ kontragentga qarzdormiz (kreditor: supplier qarzi,
                 xodim maoshi, mijoz avansi ...)
"""

import frappe
from frappe import _
from frappe.utils import flt, fmt_money

from erpnext.accounts.utils import get_balance_on


@frappe.whitelist()
def get_party_balance(party_type, party, company=None, date=None):
	"""Kontragentning sanagacha bo'lgan GL-qoldig'i + tayyor ko'rsatma matni."""
	if not (party_type and party):
		return None

	# get_balance_on frappe.form_dict'dagi "account"/"date" qiymatlarini ham
	# o'qiydi — begona kalitlar aralashmasligi uchun aniq argument beramiz.
	company = company or frappe.defaults.get_user_default("Company") \
		or frappe.db.get_single_value("Global Defaults", "default_company")

	# in_account_currency=False — qoldiq KOMPANIYA valyutasida (aks holda har
	# hisob o'z valyutasida yig'ilib, ko'p-valyutali kontragentda ma'nosiz
	# aralash summa chiqadi; yorliq/formatlash ham kompaniya valyutasida).
	balance = flt(
		get_balance_on(
			party_type=party_type,
			party=party,
			company=company,
			date=date or None,
			in_account_currency=False,
		),
		2,
	)

	currency = frappe.get_cached_value("Company", company, "default_currency")
	formatted = fmt_money(abs(balance), currency=currency)

	if balance > 0:
		message = _("контрагент должен нам")
		indicator = "blue"
	elif balance < 0:
		message = _("мы должны контрагенту")
		indicator = "orange"
	else:
		message = _("задолженности нет")
		indicator = "green"

	return {
		"balance": balance,
		"formatted": formatted,
		"message": message,
		"indicator": indicator,
		"currency": currency,
	}
