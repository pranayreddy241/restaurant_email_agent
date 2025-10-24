# Email Replier Agent

This repository contains a simple Python‑based email agent designed for a restaurant mailbox.  It automatically reads incoming messages, classifies them as reservation enquiries or feedback, and responds appropriately:

* **Reservation enquiries** –  The agent looks for emails containing reservation‑related keywords (e.g. “reservation”, “book a table”).  If the message includes the reservation time and number of guests, the agent sends a confirmation reply.  If either the time or the number of guests is missing, the agent sends a polite request asking the sender to provide the missing information.  Reservation replies are sent immediately as these requests are time‑sensitive.

* **Feedback emails** –  Messages containing words like “feedback”, “review” or “complaint” are treated as feedback.  Instead of replying automatically, the agent generates a draft reply thanking the customer for their input and saves it to a local `drafts/` directory.  The restaurant owner can review and edit these drafts before sending.

Emails that do not fall into either category are ignored.

The agent uses standard IMAP and SMTP protocols, so it works with most email providers (Gmail, Outlook, Yahoo, etc.).  Credentials are not hard‑coded; instead they can be provided via environment variables or modified in the configuration section of the script.  For Gmail accounts you may need to create an **App Password** or enable **Less secure app access** in your account settings.

## Features

* Connects to an IMAP server, fetches unread emails and parses their content.
* Detects reservation and feedback keywords.
* Parses reservation emails to determine whether a time and number of guests are mentioned.
* Sends replies via SMTP for reservation enquiries.
* Saves feedback replies as drafts for later review.
* Marks processed emails as read so they are not handled twice.

## Installation

1. **Clone or download** this repository.

2. Install the required Python packages.  Create a virtual environment if desired:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Set your email credentials as environment variables or edit the configuration variables at the top of `main.py`.

```bash
export EMAIL_ADDRESS="your_email@example.com"
export EMAIL_PASSWORD="your_email_password"
export IMAP_SERVER="imap.yourprovider.com"       # e.g. imap.gmail.com
export SMTP_SERVER="smtp.yourprovider.com"       # e.g. smtp.gmail.com
export SMTP_PORT=587                               # adjust as needed
```

On Gmail you may need to generate an App Password and use that value for `EMAIL_PASSWORD`.

## Usage

To run the agent once:

```bash
python main.py
```

When invoked, the script will:

1. Connect to the IMAP server and fetch unread messages from the inbox.
2. For each message, determine whether it is a reservation enquiry or feedback.
3. Send a reply for reservation emails (requesting missing information if necessary).
4. Save a draft reply for feedback emails under the `drafts/` directory.
5. Mark the message as read.

You can schedule this script to run periodically (for example with `cron`) to ensure timely responses to reservation enquiries.

## Drafts

Feedback replies are written to the `drafts/` folder as text files with a filename based on the message ID.  The owner can open these files, review or edit the reply and send it manually through their email client.  This approach avoids sending unreviewed feedback responses.

## Customisation

* **Keyword lists** –  The lists of keywords used to detect reservation and feedback emails are defined in `main.py`.  You can modify these lists to fit your own email patterns.
* **Reply templates** –  The text of the automatic replies and drafts is defined in functions `create_reservation_reply` and `create_feedback_reply`.  Feel free to customise the wording to match your restaurant’s tone and branding.

## Disclaimer

This script is provided as a sample implementation.  Sending automated emails carries the risk of incorrect classification or misinterpreting a customer’s message.  Always test thoroughly and monitor the agent’s behaviour before using it in production.  The authors are not responsible for any unintended actions or miscommunications arising from the use of this software.