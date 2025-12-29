# DKIM Troubleshooting - Final Analysis

## Current Status

**Test Email Results:**
- ✅ **SPF: PASS** - Working correctly
- ❌ **DKIM: FAIL** - "invalid public key" 
- ✅ **DMARC: PASS** - Working (because SPF passes)

## Issue Analysis

The DKIM key in DNS is being split by Cloudflare into multiple quoted strings:
```
"v=DKIM1; h=sha256; k=rsa; t=y; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuJsvz+MqZxWbArj6PSZRFEmVmEYp5NO+dBFz/SfCSmnudcVavKQSqlusA0rbn1/hpFBoQEDQddQEk5lTh9YcJAZCYL4oY2OwchGjHslCF4fvESN9JJ6FnAqElI6xbUMZOpcg9m203I6bK7T41jcT1T3R3dSe5QsB7vddPlftZaQ2QRxjDK" 
"nPq/epou7A5mWWAZdkhYaZOfmWzzVxYaOzK3Q8Fh19lcqvm61StQFrJxAJQ/j9lHb4O4S1s4W4ZiT6ZpVxJ2S439WVijQpjqQ8Gzxhfew76PExE5ojQ2BgnsnBGzuBZpyqE36p86n3ugofs95rW+Sk69zzFlmJ0ScQIDAQAB"
```

The split happens at exactly 255 characters (DNS TXT record limit per string).

## Possible Solutions

### Option 1: Wait for Full DNS Propagation
DNS changes can take up to 48 hours to fully propagate. The record was just updated, so Gmail might still be seeing the old cached record.

**Action:** Wait 24-48 hours and test again.

### Option 2: Regenerate DKIM Keys
If the keys don't match, we may need to regenerate them:

```bash
ssh mail.s0me.uk
sudo rm /etc/opendkim/keys/lexapp.co.ua/mail.*
sudo opendkim-genkey -t -s mail -d lexapp.co.ua -D /etc/opendkim/keys/lexapp.co.ua/
sudo chown opendkim:opendkim /etc/opendkim/keys/lexapp.co.ua/*
sudo systemctl restart opendkim
```

Then extract the new public key and update DNS.

### Option 3: Check Key Match Manually
Verify the public key in DNS matches what's on the server:

```bash
# Get key from DNS
dig TXT mail._domainkey.lexapp.co.ua +short | sed 's/" "//g' | sed 's/"//g' | grep -o 'p=[^;]*' | sed 's/p=//' | tr -d ' ' > /tmp/dns_key.txt

# Get key from server
ssh mail.s0me.uk "sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt | grep -oP '\"p[+=][^\"]+\"' | sed 's/\"//g' | sed 's/^p[+=]//' | tr -d '\n'" > /tmp/server_key.txt

# Compare
diff /tmp/dns_key.txt /tmp/server_key.txt
```

### Option 4: Use Shorter Key
Generate a shorter DKIM key (1024-bit instead of 2048-bit) to avoid splitting:

```bash
ssh mail.s0me.uk
sudo opendkim-genkey -b 1024 -t -s mail -d lexapp.co.ua -D /etc/opendkim/keys/lexapp.co.ua/
```

**Note:** 1024-bit keys are less secure but will fit in a single DNS TXT record.

## Current Configuration

- **Key Length:** 390 characters (2048-bit RSA)
- **DNS Record:** Split across 2 strings (Cloudflare automatic)
- **Server Key:** `/etc/opendkim/keys/lexapp.co.ua/mail.private`
- **DNS Key:** Updated with 390-character base64 key

## Recommendation

1. **Wait 24-48 hours** for full DNS propagation
2. **Send another test email** after waiting
3. **If still failing**, regenerate keys with shorter length (1024-bit)
4. **Alternative:** Check if Gmail is properly combining the split DNS strings

## Verification

After waiting, check:
```bash
# Test on server
ssh mail.s0me.uk
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private

# Check DNS from Google's perspective
dig @8.8.8.8 TXT mail._domainkey.lexapp.co.ua +short
```

## Note

Even though DKIM is failing, **SPF and DMARC are passing**, which means:
- Your emails are being accepted by Gmail
- They're not being marked as spam (due to SPF pass)
- DMARC is passing because SPF passes

DKIM failure doesn't prevent email delivery, but it's best practice to have all three passing.

