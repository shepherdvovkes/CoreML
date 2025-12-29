# Email Authentication Setup - Complete Guide

This document provides a complete guide for setting up SPF, DKIM, and DMARC for `lexapp.co.ua`.

## Current Status

### ✅ SPF Record
- **Status**: Configured
- **Record**: `v=spf1 mx a ip4:178.162.234.145 ~all`
- **Verification**: `dig TXT lexapp.co.ua`

### ✅ DMARC Record
- **Status**: Configured
- **Record**: `v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@lexapp.co.ua`
- **Verification**: `dig TXT _dmarc.lexapp.co.ua`
- **Policy**: Quarantine (emails failing authentication will be quarantined)

### ⏳ DKIM Record
- **Status**: Pending server-side configuration
- **Action Required**: Run `setup_dkim_postfix.sh` on mail server

## DNS Records Summary

| Type | Name | Value | Status |
|------|------|-------|--------|
| SPF | `lexapp.co.ua` | `v=spf1 mx a ip4:178.162.234.145 ~all` | ✅ Active |
| DMARC | `_dmarc.lexapp.co.ua` | `v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@lexapp.co.ua` | ✅ Active |
| DKIM | `mail._domainkey.lexapp.co.ua` | `v=DKIM1; k=rsa; p=<public_key>` | ⏳ Pending |

## SPF Record Details

**What it does**: Authorizes your mail server IP to send emails for your domain.

**Current Configuration**:
```
v=spf1 mx a ip4:178.162.234.145 ~all
```

**Breakdown**:
- `v=spf1` - SPF version 1
- `mx` - Allow mail servers listed in MX records
- `a` - Allow A record for the domain
- `ip4:178.162.234.145` - Allow specific IP address
- `~all` - Soft fail for all other sources (emails from unauthorized sources will be marked but not rejected)

**To make it stricter** (reject unauthorized emails):
```
v=spf1 mx a ip4:178.162.234.145 -all
```
(Change `~all` to `-all`)

## DMARC Record Details

**What it does**: Tells receiving mail servers how to handle emails that fail SPF/DKIM authentication.

**Current Configuration**:
```
v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@lexapp.co.ua
```

**Breakdown**:
- `v=DMARC1` - DMARC version 1
- `p=quarantine` - Policy: quarantine emails that fail authentication
- `pct=100` - Apply policy to 100% of emails
- `rua=mailto:dmarc@lexapp.co.ua` - Send aggregate reports to this email

**Policy Options**:
- `p=none` - Monitor only, don't take action
- `p=quarantine` - Mark as spam/quarantine (current)
- `p=reject` - Reject emails that fail authentication

**Recommendation**: Start with `quarantine` for a few weeks, then move to `reject` once everything is working.

## DKIM Setup (Server-Side)

DKIM requires configuration on your mail server (`178.162.234.145`).

### Quick Setup

1. **SSH to your mail server**:
   ```bash
   ssh user@178.162.234.145
   ```

2. **Copy the setup script**:
   ```bash
   # Copy setup_dkim_postfix.sh to your server
   scp scripts/setup_dkim_postfix.sh user@178.162.234.145:/tmp/
   ```

3. **Run the setup script**:
   ```bash
   sudo bash /tmp/setup_dkim_postfix.sh
   ```

4. **Get the public key**:
   The script will output the DKIM public key. Copy it.

5. **Add DKIM record to DNS**:
   ```bash
   python scripts/setup_email_dns.py \
     --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
     --email "shepherdvovkes@icloud.com" \
     --dkim-selector mail \
     --dkim-key "<public_key_from_server>"
   ```

### Manual Setup

If you prefer to set up DKIM manually:

1. **Install OpenDKIM**:
   ```bash
   sudo apt-get update
   sudo apt-get install opendkim opendkim-tools
   ```

2. **Generate keys**:
   ```bash
   sudo mkdir -p /etc/opendkim/keys/lexapp.co.ua
   sudo opendkim-genkey -t -s mail -d lexapp.co.ua -D /etc/opendkim/keys/lexapp.co.ua/
   sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua/*
   ```

3. **Configure OpenDKIM** (`/etc/opendkim.conf`):
   ```conf
   Domain                  lexapp.co.ua
   KeyFile                 /etc/opendkim/keys/lexapp.co.ua/mail.private
   Selector                mail
   Socket                  inet:8891@localhost
   ```

4. **Configure Postfix** (`/etc/postfix/main.cf`):
   ```conf
   milter_protocol = 2
   milter_default_action = accept
   smtpd_milters = inet:localhost:8891
   non_smtpd_milters = inet:localhost:8891
   ```

5. **Restart services**:
   ```bash
   sudo systemctl restart opendkim
   sudo systemctl restart postfix
   ```

6. **Get public key**:
   ```bash
   sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
   ```

## Verification

### Verify SPF
```bash
dig TXT lexapp.co.ua
```

Expected output:
```
"v=spf1 mx a ip4:178.162.234.145 ~all"
```

### Verify DMARC
```bash
dig TXT _dmarc.lexapp.co.ua
```

Expected output:
```
"v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@lexapp.co.ua"
```

### Verify DKIM (after setup)
```bash
dig TXT mail._domainkey.lexapp.co.ua
```

Expected output:
```
"v=DKIM1; k=rsa; p=<long_public_key>"
```

## Testing Email Authentication

### Send a Test Email

1. Send an email from your server to Gmail
2. In Gmail, open the email and click "Show original"
3. Look for these headers:
   - `SPF: PASS`
   - `DKIM: 'PASS'`
   - `DMARC: PASS`

### Online Tools

- **SPF Checker**: https://mxtoolbox.com/spf.aspx
- **DKIM Validator**: https://www.dmarcanalyzer.com/dkim-check/
- **DMARC Analyzer**: https://www.dmarcanalyzer.com/
- **Mail Tester**: https://www.mail-tester.com/

## Troubleshooting

### SPF Not Working

1. **Check DNS propagation**:
   ```bash
   dig TXT lexapp.co.ua
   ```

2. **Verify IP address**: Make sure `178.162.234.145` is your actual mail server IP

3. **Wait for propagation**: DNS changes can take 5-15 minutes

### DKIM Not Working

1. **Check OpenDKIM status**:
   ```bash
   sudo systemctl status opendkim
   ```

2. **Check OpenDKIM logs**:
   ```bash
   sudo journalctl -u opendkim -f
   ```

3. **Verify key permissions**:
   ```bash
   sudo ls -la /etc/opendkim/keys/lexapp.co.ua/
   ```
   Private key should be `600`, owned by `opendkim:opendkim`

4. **Test DKIM signing**:
   ```bash
   sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private
   ```

### DMARC Not Working

1. **Check DNS record**:
   ```bash
   dig TXT _dmarc.lexapp.co.ua
   ```

2. **Verify email address**: Make sure `dmarc@lexapp.co.ua` exists and can receive emails

3. **Check DMARC reports**: You should start receiving aggregate reports at `dmarc@lexapp.co.ua`

## Updating DNS Records

### Update SPF Record
```bash
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com"
```

### Update DMARC Record
```bash
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --setup-dmarc \
  --dmarc-policy reject \
  --dmarc-rua "dmarc@lexapp.co.ua"
```

### Add DKIM Record
```bash
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --dkim-selector mail \
  --dkim-key "<public_key>"
```

## Best Practices

1. **Start with monitoring**: Use `p=none` for DMARC initially to monitor without taking action
2. **Gradually increase strictness**: Move from `~all` to `-all` in SPF, and from `quarantine` to `reject` in DMARC
3. **Monitor reports**: Check DMARC aggregate reports regularly
4. **Keep keys secure**: DKIM private keys should have restricted permissions (600)
5. **Test before production**: Always test email authentication before sending production emails

## Next Steps

1. ✅ SPF - **Complete**
2. ✅ DMARC - **Complete**
3. ⏳ DKIM - **Run setup script on mail server**
4. ⏳ Test email sending after DKIM is configured
5. ⏳ Monitor DMARC reports for a few days
6. ⏳ Consider moving DMARC policy to `reject` after verification

## Support

For issues or questions:
- Check DNS records: `dig TXT <record_name>`
- Check server logs: `sudo journalctl -u opendkim -f`
- Use online validators (links above)

