# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""LCV taxes'ga iz-maydonlar (custom_dop_rasxod_row, custom_distribution_basis)
va PI Item Kg property-setter'lari.

Nega alohida patch: add_dop_rasxod_custom_fields saytlarda ALLAQACHON
"bajarilgan" deb belgilangan — CUSTOM_FIELDS'ga keyin qo'shilgan yangi
maydonlar migrate'da o'z-o'zidan yaratilmaydi (patch-tuzoq). Yangi nomli
patch har saytda bir marta ishlab, execute()ni qayta chaqiradi
(create_custom_fields idempotent — mavjudlariga zarar yo'q).
"""

from suviner.custom.purchase_invoice_dop_rasxod import execute as create_fields


def execute():
	create_fields()
