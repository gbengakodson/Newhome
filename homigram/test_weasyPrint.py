# test_weasyprint.py
import os
os.add_dll_directory(r"C:\Program Files\GTK3-Runtime Win64\bin")
from weasyprint import HTML

HTML(string="<h1>Hello World</h1>").write_pdf("test.pdf")
print("PDF generated successfully!")