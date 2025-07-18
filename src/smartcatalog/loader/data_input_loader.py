from docx import Document

def load_data_from_docx(filepath):
    doc = Document(filepath)
    result_lines = []

    for table in doc.tables:
        rows = table.rows
        for i, row in enumerate(rows):
            if i < 3:
                continue
            if len(row.cells) >= 3:
                content = row.cells[2].text.strip()
                if content:
                    result_lines.append(content)

    return result_lines
