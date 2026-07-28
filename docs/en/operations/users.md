# Users and Telegram bot

Manage users through the Marzban dashboard or its native Telegram bot. Mirage
does not add an administrator panel or call the API on an operator's behalf.

When issuing access:

1. Create the user with the bot or dashboard.
2. Assign all four approved inbounds.
3. Set the expiry and traffic limit.
4. Send the one HTTPS subscription URL through a secure channel.

Use native suspension or deletion to revoke access. The user refreshes the same
subscription; a new URL is unnecessary unless the account itself changes.
