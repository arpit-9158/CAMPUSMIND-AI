def generate_email_draft(recipient_role: str, subject: str, purpose: str, message: str = "") -> dict:
    body = message.strip() or f"I am writing to request assistance with {purpose.strip()}. Please let me know the required steps and any supporting documents I should provide."
    return {"label": "Email draft — not sent", "recipient_role": recipient_role.strip(), "subject": subject.strip(), "body": f"Dear {recipient_role.strip()},\n\n{body}\n\nThank you,\n[Your name]\n[Student ID]", "sent": False}
