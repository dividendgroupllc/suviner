# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Fresh-install sozlamalari.

MUHIM: frappe yangi o'rnatishda BARCHA patchlarni "bajarilgan" deb belgilaydi
(set_all_patches_as_completed) — shuning uchun maydon-yaratuvchi patchlar yangi
saytda hech qachon ishlamaydi. after_install shu executelarning HAMMASINI
chaqirishi shart (barchasi idempotent).
"""


def after_install():
	from suviner.custom.party_balance_fields import execute as party_balance_fields
	from suviner.custom.purchase_invoice_dop_rasxod import execute as dop_rasxod_fields

	dop_rasxod_fields()
	party_balance_fields()
