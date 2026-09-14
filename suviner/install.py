# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Suviner sozlamalarining YAGONA kirish nuqtasi.

Barcha custom-field/property-setter "retseptlari" domen-modullarda turadi
(suviner/custom/*), shu yerdan bitta zanjir bo'lib qo'llanadi:

- after_install  — yangi saytga o'rnatilganda (fresh-installda patchlar
                   "bajarilgan" deb belgilanadi, shuning uchun bu shart);
- after_migrate  — HAR deploy/migrate'da. Retseptlar idempotent
                   (create_custom_fields/make_property_setter mavjudini
                   yangilaydi, dublikat yaratmaydi) — shuning uchun maydon
                   o'zgartirish uchun endi alohida patch YOZILMAYDI:
                   retsept-modulni o'zgartiring, push qiling — migrate o'zi
                   qo'llaydi.

Patchlar (suviner/patches/) faqat BIR MARTALIK ma'lumot-o'zgarishlar uchun
qoladi (masalan rename, backfill).
"""


def apply_customizations():
	"""Barcha maydon/sozlama-retseptlarini qo'llaydi (idempotent)."""
	from suviner.custom.kassa_source_link import execute as kassa_source_link
	from suviner.custom.party_balance_fields import execute as party_balance_fields
	from suviner.custom.purchase_invoice_dop_rasxod import execute as dop_rasxod_fields

	dop_rasxod_fields()
	party_balance_fields()
	kassa_source_link()


def after_install():
	apply_customizations()


def after_migrate():
	apply_customizations()
