#!/usr/bin/env python3
"""
Generate 24 single-use codes (3x8 A4), export CSV, and create an A4 PDF
with QR grid + scissor guides.

Outputs (timestamped):
  - codes_YYYYMMDD-HHMMSS.csv
  - sheet_YYYYMMDD-HHMMSS.pdf
"""

import csv
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from access_codes import generate_code_str
from code_file_io import save_codes_to_file
from db import create_connection, get_next_sheet_id


class CodeSetGenerator:
    
    # Layout (mm)
    _MARGIN_MM = 10
    _GUTTER_MM = 2
    _INNER_PAD_MM = 2
    _QR_SIZE_MM = 35  # square QR size inside label
    _TEXT_GAP_MM = 2  # gap between QR and text
    
    def __init__(self, cols: int = 3, rows: int = 8, start_set_no: int = 1) -> None:
        self.cols = cols
        self.rows = rows
        self.codes_per_page = cols * rows
        self.start_set_number = start_set_no
    
    def generate_codes(self, count: int, start_set_no: int = 1) -> list[tuple[int, str]]:
        """
        Generate a list of (set_no, code) tuples.
        set_no is an integer collection number (e.g. 1,2,3...) for grouping codes.
        code is the generated code string.
        """
        items = []
        for i in range(count):
            code = generate_code_str(start_set_no)
            items.append((start_set_no, code))
        return items
    
    def draw_qr(self, c: canvas.Canvas, value: str, x: float, y: float, size: float) -> None:
        """
        Draw a QR code at bottom-left (x,y) with given size (points).
        Uses reportlab QrCodeWidget rendered via a Drawing.
        """
        qr = QrCodeWidget(value)
        bounds = qr.getBounds()  # (x1,y1,x2,y2)
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]

        # Scale widget to requested size
        d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
        d.add(qr)
        renderPDF.draw(d, c, x, y)

    def make_sheet_pdf(self, pdf_path: Path, items: list[tuple[int, str]]) -> None:
        page_w, page_h = A4
        c = canvas.Canvas(str(pdf_path), pagesize=A4)

        # Available area inside margins
        margin = self._MARGIN_MM * mm
        gutter = self._GUTTER_MM * mm
        pad = self._INNER_PAD_MM * mm
        qr_size = self._QR_SIZE_MM * mm

        avail_w = page_w - 2 * margin
        avail_h = page_h - 2 * margin

        cell_w = (avail_w - (self.cols - 1) * gutter) / self.cols
        cell_h = (avail_h - (self.rows - 1) * gutter) / self.rows

        # ----- Scissor guides (light) -----
        c.saveState()
        c.setLineWidth(0.3)
        c.setStrokeGray(0.8)  # light gray

        # Border of usable area
        c.rect(margin, margin, avail_w, avail_h, stroke=1, fill=0)

        # Guide lines through gutters (center of each gutter)
        # Vertical
        for col in range(1, self.cols):
            x = margin + col * cell_w + (col - 1) * gutter + gutter / 2
            c.line(x, margin, x, margin + avail_h)

        # Horizontal
        for row in range(1, self.rows):
            y = margin + row * cell_h + (row - 1) * gutter + gutter / 2
            c.line(margin, y, margin + avail_w, y)

        # Small corner crop ticks (optional)
        tick = 4 * mm
        # bottom-left
        c.line(margin, margin, margin + tick, margin)
        c.line(margin, margin, margin, margin + tick)
        # bottom-right
        c.line(margin + avail_w - tick, margin, margin + avail_w, margin)
        c.line(margin + avail_w, margin, margin + avail_w, margin + tick)
        # top-left
        c.line(margin, margin + avail_h, margin + tick, margin + avail_h)
        c.line(margin, margin + avail_h - tick, margin, margin + avail_h)
        # top-right
        c.line(margin + avail_w - tick, margin + avail_h, margin + avail_w, margin + avail_h)
        c.line(margin + avail_w, margin + avail_h - tick, margin + avail_w, margin + avail_h)

        c.restoreState()

        # ----- Labels -----
        c.setFont("Helvetica", 9)

        idx = 0
        for r in range(self.rows):
            for col in range(self.cols):
                if idx >= len(items):
                    break

                _, code = items[idx]
                idx += 1

                # Cell origin (bottom-left)
                x0 = margin + col * (cell_w + gutter)
                # rows go top->bottom visually; compute from top
                y0 = margin + (self.rows - 1 - r) * (cell_h + gutter)

                # Content area inside cell
                x = x0 + pad
                y = y0 + pad

                # Place QR near top of cell (inside)
                qr_x = x + (cell_w - 2 * pad - qr_size) / 2
                qr_y = y0 + cell_h - pad - qr_size

                self.draw_qr(c, code, qr_x, qr_y, qr_size)

                # Code text centered under QR
                text_y = y0 + cell_h - pad - 3  # approx font height
                c.drawCentredString(x0 + cell_w / 2, text_y, code)

        c.showPage()
        c.save()

    def generate_sheets(self, out_dir: Path) -> None:
        """Generate codes and output files."""
        file_path = out_dir / "codes.txt"
        pdf_path = out_dir / "sheet.pdf"

        items = self.generate_codes(self.codes_per_page, self.start_set_number)

        save_codes_to_file(file_path, (t[1] for t in items))
        self.make_sheet_pdf(pdf_path, items)

        print(f"Text file: {file_path}")
        print(f"PDF: {pdf_path}")
        print(f"Generated {len(items)} codes: {items[0][1]} ... {items[-1][1]}")


def main():
    conn = create_connection()
    sheet_number = get_next_sheet_id(conn)
    generator = CodeSetGenerator(start_set_no=sheet_number)
    generator.generate_sheets(Path.cwd())


if __name__ == "__main__":
    main()