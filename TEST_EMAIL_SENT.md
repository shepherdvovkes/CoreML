# Test Email Sent - Verification Instructions

## ✅ Email Successfully Sent

**Email Details:**
- **From:** vladimir@lexapp.co.ua
- **To:** mcvovkes@gmail.com
- **Subject:** Test Email - SPF/DKIM/DMARC Verification
- **Message ID:** 4475816BC5E
- **Status:** ✅ **SENT** (Accepted by Gmail)
- **Server:** mail.s0me.uk (178.162.234.145)
- **Sent:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")

**Postfix Log Confirmation:**
```
status=sent (250 2.0.0 OK ... - gsmtp)
```

Gmail accepted the email, which is a good sign! Now verify the authentication.

---

## How to Verify SPF, DKIM, and DMARC in Gmail

### Step 1: Open the Email in Gmail

1. Go to Gmail and find the test email
2. Open the email

### Step 2: View Email Headers

1. Click the **three dots** (⋮) in the top right of the email
2. Select **"Show original"** (or "View original message")

### Step 3: Check Authentication Results

Look for the **"SPF", "DKIM", and "DMARC"** sections in the headers.

#### ✅ Expected Results:

**SPF:**
```
SPF: PASS with IP 178.162.234.145
```

**DKIM:**
```
DKIM: 'PASS' with domain lexapp.co.ua
```

**DMARC:**
```
DMARC: 'PASS'
```

#### 📋 What to Look For:

In the "Show original" view, you'll see sections like:

```
Authentication-Results: mx.google.com;
       spf=pass (google.com: domain of vladimir@lexapp.co.ua designates 178.162.234.145 as permitted sender) smtp.mailfrom=vladimir@lexapp.co.ua;
       dkim=pass header.i=@lexapp.co.ua header.s=mail header.b=...;
       dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=lexapp.co.ua
```

---

## Troubleshooting

### If SPF Fails:
- Check that IP `178.162.234.145` matches your server
- Verify SPF record: `dig TXT lexapp.co.ua`
- Wait for DNS propagation (can take up to 48 hours)

### If DKIM Fails:
- Check DKIM record: `dig TXT mail._domainkey.lexapp.co.ua`
- Verify OpenDKIM is signing: `sudo journalctl -u opendkim -f` (send another email)
- Check key match: `sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private`

### If DMARC Fails:
- Check DMARC record: `dig TXT _dmarc.lexapp.co.ua`
- DMARC will fail if both SPF and DKIM fail
- If SPF or DKIM passes, DMARC should pass

---

## What the Results Mean

### ✅ All PASS:
- **Perfect!** Your email authentication is working correctly
- Gmail will trust your emails
- Emails should not be marked as spam

### ⚠️ Some FAIL:
- Check the specific failing authentication method
- Review DNS records
- Check server configuration
- Wait for DNS propagation

### ❌ All FAIL:
- Review all DNS records
- Check server configuration
- Verify OpenDKIM is running and signing
- Check Postfix configuration

---

## Next Steps

1. **Check the email in Gmail** (mcvovkes@gmail.com)
2. **View the original message** to see authentication results
3. **Report the results:**
   - SPF: PASS / FAIL
   - DKIM: PASS / FAIL
   - DMARC: PASS / FAIL

4. **If all pass:** Your email authentication is fully configured! ✅
5. **If any fail:** Review the troubleshooting section above

---

## Additional Verification

You can also use online tools to verify:

- **Mail Tester**: https://www.mail-tester.com/
  - Send an email to the address they provide
  - Get a detailed score and report

- **MXToolbox SPF Check**: https://mxtoolbox.com/spf.aspx
  - Enter: `lexapp.co.ua`

- **DKIM Validator**: https://www.dmarcanalyzer.com/dkim-check/
  - Enter: `mail._domainkey.lexapp.co.ua`

---

## Server Logs

If you need to check server logs:

```bash
# Postfix logs
ssh mail.s0me.uk
sudo journalctl -u postfix -f

# OpenDKIM logs
sudo journalctl -u opendkim -f

# Send another test email and watch the logs
```

---

**Email sent successfully!** Please check your Gmail inbox (mcvovkes@gmail.com) and verify the authentication results.
