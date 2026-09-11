# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""PI dop-rasxod bo'limiga kurs-taxtasi maydonlarini qo'shadi (column break +
custom_kurs_html). Eski patch bajarilgan saytlarda yangi maydonlar
o'z-o'zidan yaratilmasligi uchun alohida nomli patch."""

from suviner.custom.purchase_invoice_dop_rasxod import execute as create_fields


def execute():
	create_fields()
