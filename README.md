# Email Automation Tool

A Python command-line application for sending emails through an SMTP server.

The application supports:

* Single plain-text emails
* HTML template emails
* Optional file attachments
* CSV-based bulk emails
* Per-recipient template values
* Delivery previews before sending
* Delivery reports for bulk operations

This project runs locally from the terminal. It is not a web application or a hosted email service.

---

## Purpose

The project provides a structured way to send individual or bulk emails without manually preparing every message.

It separates the main responsibilities into reusable modules:

* SMTP connection handling
* Email message creation
* Attachment handling
* Email validation
* HTML template processing
* Bulk recipient processing
* Logging and delivery reporting

Emails are sent only after the user reviews a delivery preview and confirms the operation.

---

## Features

### Plain-text email

Send one plain-text email with:

* Recipient address
* Subject
* Multiline message
* Optional attachment
* Delivery preview
* Confirmation before sending

### HTML template email

Send one HTML email using a template stored in the `templates` directory.

The application:

* Discovers available templates automatically
* Detects template placeholders automatically
* Asks only for the values required by the selected template
* Rejects missing or blank required values
* Escapes user-provided values before inserting them into HTML
* Generates a plain-text version automatically
* Supports optional attachments
* Shows a preview before connecting to SMTP

### Bulk email

Send emails to recipients listed in a CSV file.

Bulk delivery supports:

* Plain-text messages
* HTML template messages
* Recipient-specific CSV values
* Shared template values entered once
* Case-insensitive duplicate detection
* Invalid recipient handling
* Per-recipient failure handling
* Delivery report generation

A failure for one recipient does not stop the remaining recipients from being processed.

---

## Requirements

* Python 3.10 or newer
* An SMTP-enabled email account
* Internet access while sending emails

Install the Python dependencies listed in `requirements.txt`.

---

## Project structure

```text
Email-Automation-Tool/
├── config/
│   └── settings.py
├── email_service/
│   ├── attachment_handler.py
│   ├── email_builder.py
│   └── smtp_client.py
├── services/
│   ├── bulk_sender.py
│   ├── template_engine.py
│   └── validator.py
├── templates/
│   ├── custom.html
│   ├── interview.html
│   ├── meeting.html
│   ├── reminder.html
│   └── welcome.html
├── tests/
│   ├── test_bulk_sender.py
│   ├── test_main.py
│   └── test_template_engine.py
├── utils/
│   ├── logger.py
│   └── report.py
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── main.py
└── requirements.txt
```

---

## Setup

### 1. Clone the repository

```powershell
git clone https://github.com/varshini-1715/Email-Automation-Tool.git
cd Email-Automation-Tool
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create the environment file

Copy the example configuration:

```powershell
Copy-Item ".env.example" ".env"
```

Open `.env` and replace the example values:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
EMAIL_ADDRESS=your_sender@gmail.com
EMAIL_PASSWORD=your_smtp_password
SENDER_NAME=Email Automation Tool
LOG_LEVEL=INFO
```

Use the SMTP credential required by your email provider.

For Gmail SMTP, use an app password instead of placing the normal Google account password in this file.

The `.env` file contains private credentials and must never be committed to Git.

---

## Run the application

```powershell
python main.py
```

The main menu displays:

```text
1. Plain Text Email
2. Template Email
3. Bulk Email
4. Exit
```

---

## Plain-text email usage

Choose:

```text
1. Plain Text Email
```

The application asks for:

1. Recipient email address
2. Subject
3. Multiline email body
4. Optional attachment
5. Final confirmation

Finish the multiline body by pressing Enter on an empty line.

---

## Template email usage

Choose:

```text
2. Template Email
```

The application displays all `.html` files available in the `templates` directory.

After selecting a template, it:

1. Reads the placeholders from the template
2. Requests the required values
3. Generates the HTML email
4. Creates a plain-text alternative
5. Requests an optional attachment
6. Displays a delivery preview
7. Sends only after confirmation

Placeholder names do not need to be entered manually.

---

## Template format

Templates use double curly braces for placeholders.

Both formats are supported:

```html
{{recipient_name}}
{{ recipient_name }}
```

Example:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Welcome</title>
</head>
<body>
    <h1>Welcome, {{ recipient_name }}</h1>

    <p>
        Your account ID is {{ account_id }}.
    </p>

    <p>
        <a href="{{ login_link }}">Open your account</a>
    </p>

    <p>
        Regards,<br>
        {{ sender_name }}
    </p>
</body>
</html>
```

To add another template:

1. Create a new `.html` file inside `templates`
2. Add the required placeholders
3. Run the application again

The new template will appear automatically in the template menu.

Use clear placeholder names such as:

```text
recipient_name
account_id
meeting_date
login_link
sender_name
```

---

## Bulk email CSV

Every bulk CSV file must contain an `email` column.

Example plain bulk CSV:

```csv
email
alice@example.com
bob@example.com
```

Example template bulk CSV:

```csv
email,recipient_name,account_id,registration_date
alice@example.com,Alice,ACC-001,2026-07-19
bob@example.com,Bob,ACC-002,2026-07-19
```

The CSV path may be relative:

```text
data\recipients.csv
```

or absolute:

```text
C:\Users\Name\Documents\recipients.csv
```

Quotation marks around pasted paths are removed automatically.

---

## Bulk template values

For a bulk template email, values can come from two places.

### Recipient-specific values

CSV columns provide values that differ for each recipient.

Example:

```csv
email,recipient_name,account_id
alice@example.com,Alice,ACC-001
bob@example.com,Bob,ACC-002
```

### Shared values

Values not included in the CSV are requested once.

Examples:

```text
company_name
login_link
sender_name
```

The same shared values are used for every recipient.

When the same field exists in both locations, the CSV row value takes priority over the shared value.

The CSV `email` column also provides the `recipient_email` template value automatically.

---

## Bulk delivery summary

After bulk delivery, the application displays:

```text
Total Rows
Successful
Failed
Invalid Rows
Duplicate Rows
Report
```

A CSV delivery report is written under:

```text
logs/
```

The report includes:

* Recipient
* Subject
* Delivery status
* Timestamp
* Error details when delivery fails

---

## Validation and error handling

The application handles:

* Missing CSV files
* Missing `email` columns
* Invalid email addresses
* Blank email addresses
* Duplicate recipients
* Missing template files
* Unsafe template paths
* Missing template values
* Blank template values
* Missing attachment files
* SMTP connection failures
* Individual bulk delivery failures

Invalid or duplicate CSV rows are skipped and counted in the final summary.

---

## Run the tests

The tests use mocked SMTP connections and do not send real emails.

Run:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Check Python compilation:

```powershell
python -m compileall .
```

Check formatting:

```powershell
python -m black --check .
```

---

## Security notes

* Never commit `.env`
* Never place passwords directly in Python files
* Do not publish SMTP credentials in screenshots or terminal logs
* Use only email accounts and SMTP servers you are authorized to use
* Send bulk emails only to recipients who have agreed to receive them
* Test live delivery with one or two controlled recipient addresses first
* Review the delivery preview before confirming any send operation

---

## Current scope

The current version:

* Runs as a command-line application
* Sends emails immediately after confirmation
* Uses one configured sender account
* Does not include a graphical interface
* Does not include a web interface
* Does not schedule emails for future delivery
* Does not manage provider quotas or high-volume mailing campaigns

It is intended for controlled email operations, learning, testing, and small internal workflows.

---

## License

This project is available under the MIT License.

See the `LICENSE` file for the complete license text.
