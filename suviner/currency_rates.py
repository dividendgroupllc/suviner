# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Kiritilgan valyuta kurslari taxtasi (Purchase Invoice dop-rasxod bo'limi).

Currency Exchange'dagi HAR BIR (from → to) juftlikning eng oxirgi kursi
qaytariladi — qattiq ro'yxat yo'q, yangi valyuta kiritilsa o'zi chiqadi.
Kompaniya valyutasiga tugaydigan juftliklar birinchi ko'rsatiladi.
"""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_latest_exchange_rates(company=None, date=None):
	"""date berilsa — o'sha SANA HOLATIGA ko'ra kurslar (har juftlikning
	date'gacha bo'lgan eng oxirgisi). Submit qilingan hujjat keyin ochilganda
	bugungi emas, hujjat kunidagi kurs ko'rinishi uchun — hisob-kitob ham
	aynan posting_date kursi bilan bo'ladi (get_exchange_rate shunday ishlaydi)."""
	company = company or frappe.defaults.get_user_default("Company") \
		or frappe.db.get_single_value("Global Defaults", "default_company")
	company_currency = (
		frappe.get_cached_value("Company", company, "default_currency") if company else None
	)

	# Har (from → to) juftlikning sanagacha bo'lgan ENG OXIRGISI — window
	# funksiya bilan (limit-kesish yo'q: eski juftlik ham yo'qolmaydi).
	date_cond = "where date <= %(date)s" if date else ""
	rows = frappe.db.sql(
		f"""
		select from_currency, to_currency, exchange_rate, date from (
			select from_currency, to_currency, exchange_rate, date,
				row_number() over (
					partition by from_currency, to_currency
					order by date desc, creation desc
				) as rn
			from `tabCurrency Exchange` {date_cond}
		) t where rn = 1
		""",
		{"date": date},
		as_dict=True,
	)

	rates = [
		{
			"from_currency": r.from_currency,
			"to_currency": r.to_currency,
			"exchange_rate": flt(r.exchange_rate),
			"date": str(r.date),
		}
		for r in rows
	]

	# Kompaniya valyutasiga tugaydiganlar oldinda, keyin alifbo bo'yicha.
	rates.sort(key=lambda r: (r["to_currency"] != company_currency, r["from_currency"], r["to_currency"]))

	return {"company_currency": company_currency, "rates": rates}
