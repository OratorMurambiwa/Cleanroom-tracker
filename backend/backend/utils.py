

import fitz  # PyMuPDF
import re

def extract_tasks_from_pdf(file_path):
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()

    lines = text.split('\n')
    task_lines = []

    for line in lines:
        # Match something like: 8.1 Task Title .......... 14
        match = re.match(r'^(\d+\.\d+)\s+(.*?)\.{2,}\s+\d+$', line.strip())
        if match:
            section = match.group(1)
            title = match.group(2).strip()
            task_lines.append({
                "section": section,
                "title": title
            })

    return task_lines
