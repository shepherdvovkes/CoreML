# Email DNS Setup Guide

This guide helps you configure SPF and DKIM DNS records for `lexapp.co.ua` using Cloudflare API.

**For detailed DKIM server setup instructions, see:** [`DKIM_SETUP_GUIDE.md`](./DKIM_SETUP_GUIDE.md)

## Quick Start

### 1. Set up SPF Record

```bash
# Set your Cloudflare API token
export CLOUDFLARE_API_TOKEN="your_cloudflare_api_token_here"

# Run the script
python scripts/setup_email_dns.py
```

The script will:
- ✅ Find your Cloudflare zone for `lexapp.co.ua`
- ✅ Create or update SPF TXT record: `v=spf1 mx a ip4:178.162.234.145 ~all`

### 2. Verify SPF Record

After running the script, verify the DNS record:

```bash
dig TXT lexapp.co.ua
```

You should see:
```
lexapp.co.ua.    IN    TXT    "v=spf1 mx a ip4:178.162.234.145 ~all"
```

## DKIM Setup (Optional but Recommended)

**📖 For complete step-by-step instructions, see:** [`DKIM_SETUP_GUIDE.md`](./DKIM_SETUP_GUIDE.md)

DKIM requires server-side configuration. Quick setup:

### Step 1: Install OpenDKIM on Mail Server

```bash
sudo apt-get update
sudo apt-get install opendkim opendkim-tools
```

### Step 2: Generate DKIM Key Pair

```bash
sudo mkdir -p /etc/opendkim/keys/lexapp.co.ua
sudo opendkim-genkey -t -s mail -d lexapp.co.ua -D /etc/opendkim/keys/lexapp.co.ua/
sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua/*
```

This creates:
- `/etc/opendkim/keys/lexapp.co.ua/mail.private` (private key)
- `/etc/opendkim/keys/lexapp.co.ua/mail.txt` (public key DNS record)

### Step 3: Get Public Key

```bash
sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

You'll see something like:
```
mail._domainkey.lexapp.co.ua. IN TXT "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..."
```

Extract the public key (the part after `p=`).

### Step 4: Add DKIM Record via Script

```bash
python scripts/setup_email_dns.py \
  --dkim-selector mail \
  --dkim-key "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..."
```

Or manually add in Cloudflare Dashboard:
- **Name**: `mail._domainkey.lexapp.co.ua`
- **Type**: `TXT`
- **Content**: `v=DKIM1; k=rsa; p=<your_public_key>`

### Step 5: Configure Postfix

Edit `/etc/postfix/main.cf`:

```conf
# Add DKIM milter
milter_protocol = 2
milter_default_action = accept
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891
```

### Step 6: Configure OpenDKIM

Edit `/etc/opendkim.conf`:

```conf
Domain                  lexapp.co.ua
KeyFile                 /etc/opendkim/keys/lexapp.co.ua/mail.private
Selector                mail
Socket                  inet:8891@localhost
```

### Step 7: Restart Services

```bash
sudo systemctl restart opendkim
sudo systemctl restart postfix
```

### Step 8: Verify DKIM

```bash
dig TXT mail._domainkey.lexapp.co.ua
```

## Testing Email Authentication

After setting up both SPF and DKIM:

1. Send a test email from your server
2. Check email headers in Gmail (Show original)
3. Look for:
   - `SPF: PASS`
   - `DKIM: 'PASS'`

## Troubleshooting

### SPF Not Working

- Verify DNS propagation: `dig TXT lexapp.co.ua`
- Check that IP `178.162.234.145` matches your mail server IP
- Wait 5-15 minutes for DNS propagation

### DKIM Not Working

- Verify DNS record: `dig TXT mail._domainkey.lexapp.co.ua`
- Check OpenDKIM logs: `sudo journalctl -u opendkim -f`
- Check Postfix logs: `sudo journalctl -u postfix -f`
- Verify key permissions: `sudo ls -la /etc/opendkim/keys/lexapp.co.ua/`

### Gmail Still Rejecting

- Wait 24-48 hours for DNS propagation
- Check email headers for specific error messages
- Use [MXToolbox](https://mxtoolbox.com/spf.aspx) to verify SPF
- Use [DKIM Validator](https://www.dmarcanalyzer.com/dkim-check/) to verify DKIM

## Cloudflare API Token

To get your Cloudflare API token:

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
2. Click "Create Token"
3. Use "Edit zone DNS" template
4. Select zone: `lexapp.co.ua`
5. Copy the token and set it as `CLOUDFLARE_API_TOKEN`

## Current Configuration

- **Domain**: lexapp.co.ua
- **Server IP**: 178.162.234.145
- **SPF Record**: `v=spf1 mx a ip4:178.162.234.145 ~all`
- **DKIM Selector**: `mail` (when configured)

