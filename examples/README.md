# Example Files

This directory contains safe sample files for testing the application.

## Contents

- `recipients/recipients.csv` — example CSV structure for bulk email
- `templates/sample.html` — example HTML template
- `attachments/example.pdf` — example attachment

Do not place real recipient lists, confidential documents, SMTP credentials,
or private customer data in this directory.

Runtime files should be placed in:

- `data/` for local recipient CSV files
- `attachments/` for local attachments
- `logs/` for generated logs and delivery reports

The runtime folders are ignored by Git except for their `.gitkeep` files.
