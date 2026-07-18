# Email Automation Tool

A Python command-line application for sending plain-text, HTML-template, attachment, and CSV-based bulk email through SMTP.

## Current capabilities

- Single plain-text email
- Optional file attachment
- Dynamic HTML template discovery from `templates/*.html`
- Automatic placeholder detection and readable value prompts
- Automatic plain-text fallback generation from rendered HTML
- Delivery preview and confirmation before SMTP connection
- Bulk plain-text delivery from CSV
- Per-recipient bulk template rendering using CSV columns
- Shared bulk-template values entered once in the CLI
- Case-insensitive duplicate-recipient handling
- Delivery reports under `logs/`
- Offline unit tests with mocked SMTP

## Setup

1. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and replace placeholder values locally. Never commit `.env`.

3. Run the application:

   ```powershell
   python main.py
   ```

## Template email behavior

Templates are discovered automatically. Placeholders may use either form:

```html
{{recipient_name}}
{{ recipient_name }}
```

The CLI reads the selected template and asks only for required values. Users do not type placeholder names or a plain-text fallback.

## Bulk template CSV

CSV columns supply recipient-specific values. The `email` column is mandatory and automatically supplies `recipient_email`.

```csv
email,recipient_name,account_id,registration_date
alice@example.com,Alice,ACC-001,2026-07-19
bob@example.com,Bob,ACC-002,2026-07-19
```

Template values not present as CSV columns are requested once as shared values. CSV row values override shared values.

## Verification

```powershell
python -m compileall .
python -m unittest discover -s tests -p "test_*.py" -v
```

Real SMTP tests should begin with one consenting test recipient. Bulk live tests should begin with two consenting recipients only.
