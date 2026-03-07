def process_pdf(file, db):
    text = ocr_service.extract_text(file)
    draft = llm_service.generate_invoice(text)

    saved = invoice_repository.create_draft(
        db,
        file.filename,
        text,
        json.dumps(draft)
    )

    return saved