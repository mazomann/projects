/** Extract text from a PDF. Digital PDFs only; scanned PDFs need OCR (out of scope for v1, see README). */
import { readFile } from "node:fs/promises";
import { PDFParse } from "pdf-parse";

export async function pdfToText(path: string): Promise<string> {
  const data = await readFile(path);
  const parser = new PDFParse({ data });
  try {
    const result = await parser.getText();
    const text = result.text ?? "";
    if (text.trim().length < 40) {
      throw new Error(`${path}: almost no text layer; likely a scanned PDF (needs OCR)`);
    }
    return text;
  } finally {
    await parser.destroy();
  }
}
