# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Journal Entry'ga custom_source_purchase_invoice maydonini qo'shadi
(dop-rasxod qarzdorlik-JE'si uchun; eski patchlar bajarilgan saytlarda
yangi maydon o'z-o'zidan yaratilmaydi — alohida nomli patch)."""

from suviner.custom.purchase_invoice_dop_rasxod import execute as create_fields


def execute():
	create_fields()
