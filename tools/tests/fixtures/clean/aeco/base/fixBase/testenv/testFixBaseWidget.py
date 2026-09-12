#
# Copyright 2026 AECO
#
# © AECO — all rights reserved. See the NOTICE file.
#
import sys
from pxr import FixBase

label = FixBase.Widget.GetLabel()
assert label == "fixBase-widget", label
print(">>> Test SUCCEEDED")
sys.exit(0)
