"""
Email Replier Agent
--------------------

This script connects to an email inbox via IMAP, reads unread messages and
categorises them into reservation enquiries or feedback.  Reservation emails
are answered automatically: the agent checks whether the requested time and
number of guests are provided and, if not, sends a follow‑up email asking
for the missing information.  Feedback emails are not sent immediately –
instead a draft reply is created and saved locally for the owner to review.

Before running this script you must provide valid email credentials.  You can
set the following environment variables or edit the configuration section
below directly:

* `EMAIL_ADDRESS` – the email address to log in as (e.g. restaurant@domain.com)
* `EMAIL_PASSWORD` – the account password or application‑specific password
* `IMAP_SERVER` – host name of the IMAP server (default: `imap.gmail.com`)
* `SMTP_SERVER` – host name of the SMTP server (default: `smtp.gmail.com`)
* `SMTP_PORT` – port number for SMTP (default: `587`)

If using Gmail you may need to enable IMAP access and create an App Password.

Usage::

    python main.py

"""

import email
import imaplib
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import parseaddr, formataddr
from datetime import datetime

###############################################################################
# Configuration
###############################################################################

# Email credentials and server settings.  You can override these values by
# setting environment variables before running the script.  For example:
#   export EMAIL_ADDRESS="my_email@example.com"
#   export EMAIL_PASSWORD="my_password"
#   export IMAP_SERVER="imap.example.com"
#   export SMTP_SERVER="smtp.example.com"
#   export SMTP_PORT=465

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "20131a0522@gvpce.ac.in")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "ratd rrny actg vvar")
IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT   = int(os.environ.get("IMAP_PORT", "993")) 
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

def _mask(s): 
    return "" if not s else f"{s[:2]}…{s[-2:]} (len={len(s)})"

print("[CFG] EMAIL_ADDRESS =", EMAIL_ADDRESS)
print("[CFG] EMAIL_PASSWORD =", _mask(EMAIL_PASSWORD))
assert EMAIL_PASSWORD and len(EMAIL_PASSWORD.replace(" ", "")) == 16, "App password must be 16 chars (no spaces)."

###############################################################################
# Keyword definitions
###############################################################################

# Reservation keywords – if any of these appear in an email, it is treated as
# a reservation enquiry.  You can adjust this list to match the language your
# customers typically use.
RESERVATION_KEYWORDS = [
    "reservation",
    "reserve",
    "booking",
    "book a table",
    "book for",
    "table for",
    "party of"
]

# Feedback keywords – if any of these appear in an email, it is treated as
# feedback.  You can adjust this list as needed.
FEEDBACK_KEYWORDS = [
    "feedback",
    "review",
    "complaint",
    "comment",
    "suggestion",
    "experience"
]

###############################################################################
# Helper functions
###############################################################################

def extract_plain_text(msg: email.message.EmailMessage) -> str:
    """Return the concatenated plain text content from an email message.

    The function walks through all parts of a potentially multipart message
    and extracts the `text/plain` payload.  If only HTML content is present,
    the HTML is returned as a fallback.

    Args:
        msg: The email message object.

    Returns:
        A string containing the email's text content.
    """
    text_parts = []
    html_parts = []
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == 'text/plain' and not part.get_content_disposition():
            charset = part.get_content_charset() or 'utf-8'
            try:
                text_parts.append(part.get_payload(decode=True).decode(charset, errors='replace'))
            except Exception:
                continue
        elif content_type == 'text/html' and not part.get_content_disposition():
            charset = part.get_content_charset() or 'utf-8'
            try:
                html_parts.append(part.get_payload(decode=True).decode(charset, errors='replace'))
            except Exception:
                continue
    if text_parts:
        return "\n".join(text_parts)
    # Fallback to HTML stripped of tags if no plain text parts exist
    if html_parts:
        # remove basic HTML tags for crude fallback
        stripped = re.sub('<[^<]+?>', '', "\n".join(html_parts))
        return stripped
    return ""


def contains_keyword(text: str, keywords: list) -> bool:
    """Return True if any keyword is found in the provided text (case‑insensitive)."""
    lower_text = text.lower()
    return any(keyword.lower() in lower_text for keyword in keywords)


def extract_reservation_details(text: str) -> tuple[bool, bool]:
    """Determine whether a reservation email contains time and party size.

    A variety of patterns are used to detect times (e.g. "7pm", "19:30") and
    numbers of guests (e.g. "for 2", "2 people", "party of four").

    Args:
        text: The email body text.

    Returns:
        A tuple `(has_time, has_people)` indicating whether a time and number
        of guests were detected.
    """
    # Pattern for times (matches e.g. "7pm", "7 pm", "19:00", "7:30pm")
    time_pattern = re.compile(r"\b(\d{1,2})(:\d{2})?\s*(am|pm)?\b", re.IGNORECASE)
    # Pattern for number of people (matches e.g. "for 2", "2 people", "party of four")
    people_pattern = re.compile(r"\b(?:for|party of)?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:people|persons|guests)?\b", re.IGNORECASE)

    # Search for patterns in the text
    has_time = bool(time_pattern.search(text))
    has_people = bool(people_pattern.search(text))
    return has_time, has_people


def create_reservation_reply(sender_name: str, missing_time: bool, missing_people: bool) -> str:
    """Return the body of the reply to a reservation enquiry.

    The reply is tailored depending on whether the time and party size were
    provided in the original message.

    Args:
        sender_name: Name of the person making the enquiry (if available).
        missing_time: True if the email did not specify a time.
        missing_people: True if the email did not specify the number of guests.

    Returns:
        A string containing the reply message.
    """
    greeting_name = sender_name or "there"
    lines = [f"Hello {greeting_name},",
             "\nThank you for reaching out about a reservation at our restaurant."]
    # Build message based on missing details
    if missing_time and missing_people:
        lines.append("\nWe would be happy to confirm your booking, but we need a bit more information.")
        lines.append("Could you please let us know what time you would like to dine and how many guests will be joining?")
    elif missing_time:
        lines.append("\nCould you please let us know what time you would like to dine so we can confirm your reservation?")
    elif missing_people:
        lines.append("\nCould you please tell us the number of guests in your party?")
    else:
        # If both details are present, confirm the booking
        lines.append("\nYour reservation details have been noted and we look forward to welcoming you.")
        lines.append("If you need to make any changes, please let us know.")
    lines.append("\nBest regards,\nThe Restaurant Team")
    return "\n".join(lines)


def create_feedback_reply(sender_name: str) -> str:
    """Return the body of a draft reply to a feedback message."""
    greeting_name = sender_name or "there"
    lines = [f"Hello {greeting_name},",
             "\nThank you for taking the time to share your feedback with us.",
             "We appreciate your comments and will review your message carefully.",
             "\nBest regards,\nThe Restaurant Team"]
    return "\n".join(lines)


def send_email_reply(to_address: str, subject: str, body: str, original_msg: email.message.EmailMessage) -> None:
    """Send an email reply via SMTP.

    Args:
        to_address: Recipient email address.
        subject: The subject line of the reply.
        body: The body text of the reply.
        original_msg: The original email message (used for threading headers).
    """
    msg = EmailMessage()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_address
    # Prepend "Re:" if not already present
    original_subject = original_msg.get('Subject', '')
    if original_subject.lower().startswith('re:'):
        reply_subject = original_subject
    else:
        reply_subject = f"Re: {original_subject}"
    msg['Subject'] = reply_subject
    # Include In-Reply-To and References headers for proper threading
    if original_msg.get('Message-ID'):
        msg['In-Reply-To'] = original_msg['Message-ID']
        msg['References'] = original_msg['Message-ID']
    msg.set_content(body)

    # Send the message
    try:
        # Use TLS encryption for the SMTP connection
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            if SMTP_PORT == 587:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"Sent reply to {to_address} with subject '{reply_subject}'.")
    except Exception as e:
        print(f"Error sending email to {to_address}: {e}")


def save_draft_reply(to_address: str, subject: str, body: str, original_msg: email.message.EmailMessage) -> None:
    """Save a draft reply to the local drafts/ folder.

    Feedback replies are not sent automatically; instead they are written to a
    text file so that the restaurant owner can review and send them manually.

    Args:
        to_address: Recipient email address.
        subject: The subject line of the draft.
        body: The body text of the draft.
        original_msg: The original email message (used to name the draft file).
    """
    # Ensure drafts directory exists
    drafts_dir = os.path.join(os.path.dirname(__file__), 'drafts')
    os.makedirs(drafts_dir, exist_ok=True)
    # Use the message ID or current timestamp to create a unique filename
    message_id = original_msg.get('Message-ID')
    if message_id:
        # Remove angle brackets and replace at signs to make filename safe
        safe_id = message_id.strip('<>').replace('@', '_').replace('.', '_')
    else:
        safe_id = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"draft_{safe_id}.txt"
    filepath = os.path.join(drafts_dir, filename)
    # Compose the draft content
    content_lines = [f"To: {to_address}", f"Subject: {subject}", "", body]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(content_lines))
    print(f"Saved draft reply to {filepath}.")


def process_email(imap_conn: imaplib.IMAP4_SSL, msg_num: bytes) -> None:
    """Process a single email message by number.

    Depending on its content, the email will be classified and handled.

    Args:
        imap_conn: An active IMAP connection with the INBOX selected.
        msg_num: The message sequence number or UID.
    """
    try:
        status, msg_data = imap_conn.fetch(msg_num, '(RFC822)')
        if status != 'OK':
            print(f"Failed to fetch message {msg_num.decode('utf-8', 'ignore')}: {status}")
            return
        raw_email = msg_data[0][1]
        email_message = email.message_from_bytes(raw_email)
        text = extract_plain_text(email_message)
        # Extract sender name and email
        sender = email_message.get('From', '')
        sender_name, sender_email = parseaddr(sender)

        # Classify the email
        lower_text = text.lower()
        if contains_keyword(lower_text, RESERVATION_KEYWORDS):
            # Reservation enquiry
            has_time, has_people = extract_reservation_details(lower_text)
            # Determine what is missing
            missing_time = not has_time
            missing_people = not has_people
            reply_body = create_reservation_reply(sender_name, missing_time, missing_people)
            send_email_reply(sender_email, email_message.get('Subject', ''), reply_body, email_message)
        elif contains_keyword(lower_text, FEEDBACK_KEYWORDS):
            # Feedback message – create draft reply
            draft_body = create_feedback_reply(sender_name)
            # Build subject for draft (prefix with "Re:" if not already)
            subject = email_message.get('Subject', '')
            if not subject.lower().startswith('re:'):
                subject = f"Re: {subject}"
            save_draft_reply(sender_email, subject, draft_body, email_message)
        else:
            # Not a reservation or feedback – ignore
            pass
        # Mark message as read
        imap_conn.store(msg_num, '+FLAGS', '\\Seen')
    except Exception as e:
        print(f"Error processing message {msg_num.decode('utf-8', 'ignore')}: {e}")


def run_agent() -> None:
    """Connect to the inbox, read unread messages and handle them."""
    # Connect via IMAP
    try:
        imap_conn = imaplib.IMAP4_SSL(IMAP_SERVER)
        imap_conn.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        imap_conn.select('INBOX')
    except Exception as e:
        print(f"Error connecting to IMAP server: {e}")
        return
    # Search for unread messages
    try:
        status, messages = imap_conn.search(None, 'UNSEEN')
        if status != 'OK':
            print(f"Failed to search inbox: {status}")
            imap_conn.logout()
            return
        message_numbers = messages[0].split()
        if not message_numbers:
            print("No new messages to process.")
        for num in message_numbers:
            process_email(imap_conn, num)
    finally:
        # Always close the connection
        try:
            imap_conn.close()
        except Exception:
            pass
        imap_conn.logout()


if __name__ == '__main__':
    run_agent()
