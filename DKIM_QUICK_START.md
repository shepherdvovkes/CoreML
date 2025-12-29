# DKIM Quick Start for lexapp.co.ua

**Quick reference for setting up DKIM on mail server.**

## Automated Setup (Recommended)

```bash
# 1. Copy script to server
scp scripts/setup_dkim_postfix.sh user@178.162.234.145:/tmp/

# 2. SSH to server
ssh user@178.162.234.145

# 3. Run script
sudo bash /tmp/setup_dkim_postfix.sh

# 4. Copy the public key from output

# 5. Add to DNS (from local machine)
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --dkim-selector mail \
  --dkim-key "<public_key_from_script>"
```

## Manual Setup (5 Steps)

```bash
# 1. Install
sudo apt-get install opendkim opendkim-tools

# 2. Generate keys
sudo mkdir -p /etc/opendkim/keys/lexapp.co.ua
sudo opendkim-genkey -t -s mail -d lexapp.co.ua -D /etc/opendkim/keys/lexapp.co.ua/
sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua/*

# 3. Configure OpenDKIM
sudo nano /etc/opendkim.conf
# Add: Domain lexapp.co.ua, KeyFile /etc/opendkim/keys/lexapp.co.ua/mail.private, Selector mail

# 4. Configure Postfix
sudo nano /etc/postfix/main.cf
# Add: milter_protocol = 2, smtpd_milters = inet:localhost:8891

# 5. Restart
sudo systemctl restart opendkim postfix

# 6. Get public key
sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

## Verify

```bash
# Test key
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private

# Check DNS
dig TXT mail._domainkey.lexapp.co.ua

# Check status
sudo systemctl status opendkim
```

## Full Documentation

- **Complete Guide**: [`DKIM_SETUP_GUIDE.md`](./DKIM_SETUP_GUIDE.md) - Detailed step-by-step instructions
- **Email Authentication**: [`EMAIL_AUTHENTICATION_SETUP.md`](./EMAIL_AUTHENTICATION_SETUP.md) - SPF, DKIM, DMARC overview

