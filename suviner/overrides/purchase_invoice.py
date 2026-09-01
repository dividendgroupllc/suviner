# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Purchase Invoice "Доп. расход" (Landed Cost) oqimi.

- validate:  har bir доп-расход qatori uchun valyuta / kurs / baz. summani to'ldiradi
             va LCV ishlashi uchun "Update Stock"ni majburiy yoqadi; Kg-usul uchun
             og'irliklarni tekshiradi (draftda ogohlantirish, submitda qat'iy).
- on_submit: HAR BIR доп-расход qatori uchun alohida Landed Cost Voucher yaratadi
             ("Distribute Manually" rejimida, ulushlar o'zimizda hisoblanadi) —
             chunki qatorlar har xil usul bilan taqsimlanishi mumkin (Qty/Amount/Kg),
             ERPNext LCV esa butun voucher uchun bitta usulnigina biladi va
             "Distribute Manually"da faqat bitta taxes qatoriga ruxsat beradi.
- on_cancel: PI cancel qilinganda unga bog'liq LCV(lar)ni avval cancel qiladi
             (back-link tekshiruvidan oldin ishlaydi).

Taqsimlash usuli (har qator uchun alohida, bo'sh bo'lsa hujjatdagi umumiy usul):
  Qty    — miqdor (qty) nisbatida
  Amount — baza summasi nisbatida
  Kg     — og'irlik nisbatida: weight_per_unit ("Кг (за ед.)") × stock_qty
Yaxlitlash: eng katta qoldiq usuli — qator summasi tiyingacha aniq taqsimlanadi.
"""

import frappe
from frappe import _
from frappe.utils import flt
from erpnext.setup.utils import get_exchange_rate


def _has_dop_rasxod(doc):
	return bool(doc.get("custom_dop_rasxod")) and bool(doc.get("custom_dop_rasxod_items"))


def _effective_basis(doc, row):
	"""Qator uchun amaldagi taqsimlash usuli: qatorniki, bo'lmasa hujjatniki."""
	basis = row.get("distribute_based_on") or doc.get("custom_distribute_charges_based_on") or "Amount"
	if basis not in ("Qty", "Amount", "Kg"):
		# Eski hujjatlarda "Distribute Manually" saqlanib qolgan bo'lishi mumkin.
		basis = "Amount"
	return basis


def _lcv_eligible_items(doc):
	"""LCV'ga kiradigan item qatorlari — faqat stock yoki asosiy vosita.

	ERPNext get_items_from_purchase_receipts xuddi shu filtr bilan ishlaydi
	(is_stock_item=1 yoki is_fixed_asset=1); xizmat-qatorlarga ulush ajratsak,
	u LCV'ga tushmay, yig'indi mos kelmay submit yiqiladi.
	"""
	items = list(doc.get("items") or [])
	if not items:
		return []
	flags = {
		r.name: r
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", list({it.item_code for it in items})]},
			fields=["name", "is_stock_item", "is_fixed_asset"],
		)
	}
	return [
		it
		for it in items
		if (f := flags.get(it.item_code)) and (f.is_stock_item or f.is_fixed_asset)
	]


def _item_weights(doc, basis):
	"""LCV'ga kiradigan item'lar uchun taqsimlash vaznlari (kalit — qator name'i)."""
	weights = {}
	for it in _lcv_eligible_items(doc):
		if basis == "Qty":
			weights[it.name] = flt(it.qty)
		elif basis == "Kg":
			weights[it.name] = flt(it.weight_per_unit) * flt(it.stock_qty or it.qty)
		else:  # Amount
			weights[it.name] = flt(it.base_amount) or flt(it.base_net_amount)
	return weights


def _allocate(total, weights, precision=2):
	"""total'ni weights nisbatida taqsimlaydi; yig'indi AYNAN total bo'ladi.

	Eng katta qoldiq usuli: har ulush yaxlitlangach, tiyin-farq eng katta
	qoldiqli qatorlarga 0.01 qadam bilan tarqatiladi. Vaznlar yig'indisi 0
	bo'lsa None qaytadi (chaqiruvchi xato beradi).
	"""
	total = flt(total, precision)
	positive = {k: flt(w) for k, w in weights.items() if flt(w) > 0}
	total_weight = sum(positive.values())
	if total_weight <= 0:
		return None

	step = round(10**-precision, precision)
	alloc = {k: 0.0 for k in weights}
	remainders = []
	allocated = 0.0
	for key, weight in positive.items():
		exact = total * weight / total_weight
		rounded = flt(exact, precision)
		alloc[key] = rounded
		remainders.append([exact - rounded, key])
		allocated = flt(allocated + rounded, precision)

	diff = flt(total - allocated, precision)
	remainders.sort(key=lambda r: r[0], reverse=diff > 0)
	i = 0
	while abs(diff) >= step / 2 and remainders:
		key = remainders[i % len(remainders)][1]
		delta = step if diff > 0 else -step
		alloc[key] = flt(alloc[key] + delta, precision)
		diff = flt(diff - delta, precision)
		i += 1
	return alloc


def _validate_kg_rows(doc, strict):
	"""Kg-usulli qatorlar uchun og'irliklar tekshiruvi.

	strict=False (draft saqlash) — faqat ogohlantirish; strict=True (submit) —
	og'irliklar umuman yo'q bo'lsa frappe.throw (aks holda taqsimlab bo'lmaydi).
	"""
	kg_rows = [
		row for row in (doc.get("custom_dop_rasxod_items") or [])
		if _effective_basis(doc, row) == "Kg"
	]
	if not kg_rows:
		return

	weights = _item_weights(doc, "Kg")
	zero_items = [
		it.item_code for it in _lcv_eligible_items(doc) if flt(weights.get(it.name)) <= 0
	]
	if sum(weights.values()) <= 0:
		message = _(
			"Доп-расходда Kg усули танланган, лекин бирорта товарда «Кг (за ед.)» киритилмаган — оғирлик бўйича тақсимлаб бўлмайди."
		)
		if strict:
			frappe.throw(message)
		frappe.msgprint(message, indicator="orange", alert=True)
	elif zero_items:
		frappe.msgprint(
			_("Kg усулида қуйидаги товарлар оғирлиги 0 — уларга доп-расход улуши тушмайди: {0}").format(
				", ".join(zero_items)
			),
			indicator="orange",
			alert=True,
		)


def validate(doc, method=None):
	if not doc.get("custom_dop_rasxod"):
		return

	# Landed Cost Voucher faqat "Update Stock" yoqilgan PI bilan ishlaydi.
	if not doc.update_stock:
		doc.update_stock = 1
		frappe.msgprint(
			_("«Доп. расход» белгиланган — Landed Cost учун «Update Stock» автоматик ёқилди."),
			indicator="orange",
			alert=True,
		)

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")

	for row in doc.get("custom_dop_rasxod_items") or []:
		# DOIM ta'minotchidan qayta aniqlaymiz: maydon read-only (manbasi shu),
		# erpnext validate esa "currency" nomli child-maydonlarga hujjat
		# valyutasini yozib qo'yishi mumkin (bizning hookdan OLDIN ishlaydi).
		row.currency = (
			frappe.db.get_value("Supplier", row.supplier, "default_currency")
			or company_currency
		)

		if row.currency == company_currency:
			row.exchange_rate = 1
		elif not flt(row.exchange_rate) or flt(row.exchange_rate) == 1:
			# rate=1 chet valyuta uchun deyarli har doim noto'g'ri (erpnext
			# scribble'i) — qaytadan olamiz; topilmasa jim 1 o'rniga xato.
			rate = get_exchange_rate(row.currency, company_currency, doc.posting_date)
			if not rate:
				frappe.throw(
					_("{0} → {1} курси топилмади — Currency Exchange ёзувини яратинг.").format(
						row.currency, company_currency
					)
				)
			row.exchange_rate = rate

		row.base_amount = flt(
			flt(row.amount) * flt(row.exchange_rate), row.precision("base_amount")
		)

	# Submit paytida validate docstatus=1 bilan ishlaydi — Kg tekshiruvi shunda
	# qat'iy bo'ladi (Kassa saboqlari: docstatus o'zgarishidan OLDIN tekshirish).
	_validate_kg_rows(doc, strict=(doc.docstatus == 1))


def on_submit(doc, method=None):
	if not doc.get("custom_dop_rasxod"):
		return

	if not doc.get("custom_dop_rasxod_items"):
		frappe.throw(_("«Доп. расход» белгиланган, лекин харажат қаторлари киритилмаган."))

	create_landed_cost_voucher(doc)


def create_landed_cost_voucher(doc):
	"""PI submit bo'lgach HAR BIR доп-расход qatori uchun alohida LCV yaratadi.

	Har LCV "Distribute Manually" rejimida: item ulushlari qatorning o'z usuli
	(Qty/Amount/Kg) bo'yicha _allocate bilan tiyingacha aniq hisoblab beriladi.
	ERPNext cheklovi: manual-LCV'da faqat bitta taxes qatori bo'lishi mumkin —
	shuning uchun qator-boshiga bitta voucher (rasmiy tavsiya qilingan yo'l).
	"""

	# Bitta PI uchun ikki marta yaratilmasin (amend/qayta submit holatlari uchun).
	existing = frappe.db.exists(
		"Landed Cost Purchase Receipt",
		{
			"receipt_document_type": "Purchase Invoice",
			"receipt_document": doc.name,
			"docstatus": 1,
		},
	)
	if existing:
		return

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	created_links = []

	for idx, row in enumerate(doc.custom_dop_rasxod_items, start=1):
		if not flt(row.base_amount):
			frappe.msgprint(
				_("Доп-расход қатори #{0}: сумма 0 — ўтказиб юборилди.").format(idx),
				indicator="orange",
				alert=True,
			)
			continue

		basis = _effective_basis(doc, row)
		alloc = _allocate(flt(row.base_amount), _item_weights(doc, basis))
		if alloc is None:
			frappe.throw(
				_("Доп-расход қатори #{0} ({1} усули): тақсимлаш вазнлари 0 — тақсимлаб бўлмайди.").format(
					idx, basis
				)
			)

		lcv = frappe.new_doc("Landed Cost Voucher")
		lcv.company = doc.company
		lcv.posting_date = doc.posting_date
		lcv.distribute_charges_based_on = "Distribute Manually"

		lcv.append(
			"purchase_receipts",
			{
				"receipt_document_type": "Purchase Invoice",
				"receipt_document": doc.name,
				"supplier": doc.supplier,
				"posting_date": doc.posting_date,
				"grand_total": doc.base_grand_total,
			},
		)
		lcv.get_items_from_purchase_receipts()

		# Summa kompaniya валютасига ўтказилган (base_amount) ҳолда узатилади,
		# шунинг учун account_currency = company_currency, exchange_rate = 1.
		lcv.append(
			"taxes",
			{
				"expense_account": row.expense_account,
				"description": (
					f"{row.supplier}: {row.description} [{basis}]"
					if row.description
					else f"{row.supplier} [{basis}]"
				),
				"amount": flt(row.base_amount),
				"account_currency": company_currency,
				"exchange_rate": 1,
				# Sebestoimost reporti uchun aniq iz: qaysi rasxod-qatordan.
				"custom_dop_rasxod_row": row.name,
				"custom_distribution_basis": basis,
			},
		)

		# LCV item'lari PI item qatoriga purchase_receipt_item orqali bog'langan.
		for lcv_item in lcv.items:
			lcv_item.applicable_charges = flt(alloc.get(lcv_item.purchase_receipt_item), 2)

		lcv.flags.ignore_permissions = True
		lcv.insert()
		lcv.submit()
		created_links.append(frappe.utils.get_link_to_form("Landed Cost Voucher", lcv.name))

	if created_links:
		frappe.msgprint(
			_("Landed Cost Voucher(лар) яратилди ва submit қилинди: {0}").format(
				", ".join(created_links)
			),
			indicator="green",
			alert=True,
		)


def before_cancel(doc, method=None):
	if not doc.get("custom_dop_rasxod"):
		return

	# LCV'larni PI hali submitted holatida (before_cancel) bekor qilamiz:
	# LCV canceli receipt'ni qayta repost qiladi — bu PI'ning O'Z stock/GL
	# bekor qilinishidan KEYIN bo'lsa, bekor qilingan SLE'lar qayta "tirilib"
	# aktiv arvoh-yozuvlar qoladi (2026-09-01 da aniqlangan bug). before_cancel
	# tartibida: LCV repost → toza pre-LCV holat → PI o'zini toza bekor qiladi;
	# back-link tekshiruvi ham o'tadi (LCV'lar allaqachon cancelled).
	links = frappe.get_all(
		"Landed Cost Purchase Receipt",
		filters={
			"receipt_document_type": "Purchase Invoice",
			"receipt_document": doc.name,
		},
		pluck="parent",
	)

	for lcv_name in set(links):
		lcv = frappe.get_doc("Landed Cost Voucher", lcv_name)
		if lcv.docstatus == 1:
			lcv.flags.ignore_permissions = True
			lcv.cancel()
