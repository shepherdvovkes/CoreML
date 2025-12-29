# DKIM Setup Guide for lexapp.co.ua Mail Server

This guide provides step-by-step instructions for setting up DKIM email signing on your mail server (`178.162.234.145`) for the domain `lexapp.co.ua`.

## Prerequisites

- SSH access to your mail server (178.162.234.145)
- Root or sudo access
- Postfix mail server already installed and configured
- Domain: `lexapp.co.ua`
- Mail server IP: `178.162.234.145`

## Overview

DKIM (DomainKeys Identified Mail) adds a cryptographic signature to your emails, allowing receiving servers to verify that emails actually came from your domain and haven't been tampered with.

**What we'll do:**
1. Install OpenDKIM
2. Generate DKIM key pair
3. Configure OpenDKIM
4. Configure Postfix to use DKIM
5. Add DKIM public key to DNS
6. Test and verify

---

## Method 1: Automated Setup (Recommended)

### Step 1: Copy Setup Script to Server

From your local machine:

```bash
# Copy the setup script to your server
scp scripts/setup_dkim_postfix.sh user@178.162.234.145:/tmp/setup_dkim.sh

# Or if you have the script locally, upload it via SFTP
```

### Step 2: SSH to Your Mail Server

```bash
ssh user@178.162.234.145
```

### Step 3: Run the Setup Script

```bash
# Make script executable
chmod +x /tmp/setup_dkim.sh

# Run with sudo
sudo bash /tmp/setup_dkim.sh
```

The script will:
- Install OpenDKIM if not already installed
- Generate DKIM keys
- Configure OpenDKIM
- Configure Postfix
- Restart services
- Display the public key for DNS

### Step 4: Copy the DKIM Public Key

The script will output something like:

```
DKIM Public Key (add this to DNS):
-----------------------------------
mail._domainkey.lexapp.co.ua. IN TXT "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..." (long key)
```

**Copy the entire content** (the part in quotes after `p=`).

### Step 5: Add DKIM Record to DNS

From your local machine, run:

```bash
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --dkim-selector mail \
  --dkim-key "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..."
```

Replace `MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC...` with the actual public key from Step 4.

### Step 6: Verify Setup

```bash
# On your local machine, verify DNS record
dig TXT mail._domainkey.lexapp.co.ua

# On the server, test DKIM signing
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private
```

If everything is correct, you should see: `key OK`

---

## Method 2: Manual Setup

If you prefer to set up DKIM manually, follow these steps:

### Step 1: Install OpenDKIM

```bash
# Update package list
sudo apt-get update

# Install OpenDKIM and tools
sudo apt-get install -y opendkim opendkim-tools
```

### Step 2: Create Directory for DKIM Keys

```bash
# Create directory structure
sudo mkdir -p /etc/opendkim/keys/lexapp.co.ua

# Set proper ownership and permissions
sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua
sudo chmod 700 /etc/opendkim/keys/lexapp.co.ua
```

### Step 3: Generate DKIM Key Pair

```bash
# Generate keys with selector "mail"
sudo opendkim-genkey -t -s mail -d lexapp.co.ua -D /etc/opendkim/keys/lexapp.co.ua/

# Set proper permissions
sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua/*
sudo chmod 600 /etc/opendkim/keys/lexapp.co.ua/mail.private
sudo chmod 644 /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

**Important files created:**
- `/etc/opendkim/keys/lexapp.co.ua/mail.private` - Private key (keep secret!)
- `/etc/opendkim/keys/lexapp.co.ua/mail.txt` - Public key for DNS

### Step 4: View the Public Key

```bash
sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

You'll see output like:
```
mail._domainkey.lexapp.co.ua. IN TXT "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..." (long key)
```

**Extract the public key**: Copy everything after `p=` and before the closing quote.

### Step 5: Configure OpenDKIM

Edit the OpenDKIM configuration file:

```bash
sudo nano /etc/opendkim.conf
```

Replace or add the following configuration:

```conf
# OpenDKIM configuration for lexapp.co.ua

# Basic settings
Syslog                  yes
SyslogSuccess           yes
LogWhy                  yes

# Signing settings
Canonicalization        relaxed/simple
Mode                    sv
SubDomains              no

# Domain and key settings
Domain                  lexapp.co.ua
KeyFile                 /etc/opendkim/keys/lexapp.co.ua/mail.private
Selector                mail

# Socket settings
Socket                  inet:8891@localhost
PidFile                 /var/run/opendkim/opendkim.pid
UMask                   022
UserID                  opendkim:opendkim

# Trusted hosts
InternalHosts           refile:/etc/opendkim/TrustedHosts
ExternalIgnoreList      refile:/etc/opendkim/TrustedHosts
```

Save and exit (Ctrl+X, then Y, then Enter).

### Step 6: Create Trusted Hosts File

```bash
sudo nano /etc/opendkim/TrustedHosts
```

Add the following:

```
127.0.0.1
localhost
lexapp.co.ua
*.lexapp.co.ua
```

Save and exit.

### Step 7: Create PID Directory

```bash
sudo mkdir -p /var/run/opendkim
sudo chown opendkim:opendkim /var/run/opendkim
```

### Step 8: Configure Postfix

Edit the Postfix main configuration:

```bash
sudo nano /etc/postfix/main.cf
```

Add the following lines at the end of the file:

```conf
# OpenDKIM milter configuration
milter_protocol = 2
milter_default_action = accept
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891
```

**Note**: If you already have milter settings, make sure they're compatible. You may need to combine them.

Save and exit.

### Step 9: Restart Services

```bash
# Restart OpenDKIM
sudo systemctl restart opendkim

# Enable OpenDKIM to start on boot
sudo systemctl enable opendkim

# Restart Postfix
sudo systemctl restart postfix

# Check status
sudo systemctl status opendkim
sudo systemctl status postfix
```

### Step 10: Add DKIM Record to DNS

Use the public key from Step 4 and add it to Cloudflare DNS:

**Option A: Using the script**

```bash
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --dkim-selector mail \
  --dkim-key "<public_key_from_step_4>"
```

**Option B: Manual DNS entry in Cloudflare**

1. Go to Cloudflare Dashboard → DNS → Records
2. Click "Add record"
3. Set:
   - **Type**: TXT
   - **Name**: `mail._domainkey`
   - **Content**: `v=DKIM1; k=rsa; p=<your_public_key>`
   - **TTL**: Auto (or 3600)
4. Click "Save"

---

## Verification and Testing

### 1. Check OpenDKIM Status

```bash
sudo systemctl status opendkim
```

Should show: `Active: active (running)`

### 2. Test DKIM Key

```bash
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private
```

Expected output: `key OK`

### 3. Verify DNS Record

```bash
dig TXT mail._domainkey.lexapp.co.ua
```

Should return the DKIM record with your public key.

### 4. Check OpenDKIM Logs

```bash
sudo journalctl -u opendkim -f
```

Send a test email and watch for signing activity.

### 5. Send Test Email

Send an email from your server to Gmail:

```bash
echo "Test email" | mail -s "DKIM Test" your-email@gmail.com
```

Then in Gmail:
1. Open the email
2. Click the three dots → "Show original"
3. Look for: `DKIM-Signature:` header
4. Check authentication results: `DKIM: 'PASS'`

### 6. Online DKIM Validator

Use an online tool to verify:
- https://www.dmarcanalyzer.com/dkim-check/
- Enter: `mail._domainkey.lexapp.co.ua`
- Should show: "DKIM Record Found" and "Valid"

---

## Troubleshooting

### OpenDKIM Not Starting

**Check logs:**
```bash
sudo journalctl -u opendkim -n 50
```

**Common issues:**
- Wrong file permissions: `sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua/*`
- Missing directory: `sudo mkdir -p /var/run/opendkim && sudo chown opendkim:opendkim /var/run/opendkim`
- Port conflict: Check if port 8891 is in use: `sudo netstat -tlnp | grep 8891`

### Emails Not Being Signed

**Check Postfix configuration:**
```bash
sudo postconf | grep milter
```

Should show:
```
milter_default_action = accept
milter_protocol = 2
non_smtpd_milters = inet:localhost:8891
smtpd_milters = inet:localhost:8891
```

**Check OpenDKIM is receiving connections:**
```bash
sudo journalctl -u opendkim -f
```

Send a test email and watch for activity.

### DKIM Test Fails

**Verify key file:**
```bash
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private -vvv
```

**Check DNS record matches:**
```bash
# Get public key from DNS
dig TXT mail._domainkey.lexapp.co.ua +short

# Compare with local key
sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

The public key in DNS should match the one in `mail.txt`.

### Gmail Shows DKIM: FAIL

1. **Wait for DNS propagation** (5-15 minutes)
2. **Verify DNS record is correct**: `dig TXT mail._domainkey.lexapp.co.ua`
3. **Check key matches**: Compare DNS public key with `mail.txt`
4. **Check OpenDKIM is signing**: Look at email headers for `DKIM-Signature:`
5. **Verify domain in OpenDKIM config**: Should be `lexapp.co.ua`

### Permission Denied Errors

```bash
# Fix ownership
sudo chown -R opendkim:opendkim /etc/opendkim/keys/
sudo chown opendkim:opendkim /var/run/opendkim

# Fix permissions
sudo chmod 600 /etc/opendkim/keys/lexapp.co.ua/mail.private
sudo chmod 644 /etc/opendkim/keys/lexapp.co.ua/mail.txt
sudo chmod 700 /etc/opendkim/keys/lexapp.co.ua
```

---

## Configuration Files Summary

| File | Purpose | Location |
|------|---------|----------|
| OpenDKIM Config | Main configuration | `/etc/opendkim.conf` |
| Private Key | DKIM signing key | `/etc/opendkim/keys/lexapp.co.ua/mail.private` |
| Public Key | DNS record content | `/etc/opendkim/keys/lexapp.co.ua/mail.txt` |
| Trusted Hosts | Internal hosts list | `/etc/opendkim/TrustedHosts` |
| Postfix Config | Milter settings | `/etc/postfix/main.cf` |

---

## Security Best Practices

1. **Protect private key**: Keep `/etc/opendkim/keys/lexapp.co.ua/mail.private` secure
   - Permissions: `600` (read/write for owner only)
   - Owner: `opendkim:opendkim`

2. **Regular key rotation**: Consider rotating DKIM keys annually

3. **Monitor logs**: Regularly check OpenDKIM logs for issues

4. **Backup keys**: Backup your DKIM keys securely

---

## Quick Reference Commands

```bash
# Check OpenDKIM status
sudo systemctl status opendkim

# View OpenDKIM logs
sudo journalctl -u opendkim -f

# Test DKIM key
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private

# Verify DNS record
dig TXT mail._domainkey.lexapp.co.ua

# Restart services
sudo systemctl restart opendkim
sudo systemctl restart postfix

# View public key
sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

---

## Next Steps

After DKIM is set up:

1. ✅ Verify DKIM is working (send test email to Gmail)
2. ✅ Check DMARC reports (you should receive them at `dmarc@lexapp.co.ua`)
3. ✅ Monitor for a few days to ensure everything is working
4. ✅ Consider moving DMARC policy from `quarantine` to `reject` after verification

---

## Support

If you encounter issues:

1. Check OpenDKIM logs: `sudo journalctl -u opendkim -n 100`
2. Check Postfix logs: `sudo journalctl -u postfix -n 100`
3. Verify DNS: `dig TXT mail._domainkey.lexapp.co.ua`
4. Test key: `sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private`

For more information, see:
- `EMAIL_AUTHENTICATION_SETUP.md` - Complete email authentication guide
- `EMAIL_DNS_SETUP.md` - DNS setup reference

