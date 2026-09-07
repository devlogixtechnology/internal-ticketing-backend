# BE7 Whitelisting Demo

Use the Django shell to create one strict client and one grace-mode client:

```powershell
python manage.py shell
```

```python
from apps.clients.models import Client, WhitelistedDomain, WhitelistedIP

strict = Client.objects.create(name="Demo Strict", code="demo-strict", enforce_whitelisting=True)
grace = Client.objects.create(name="Demo Grace", code="demo-grace", enforce_whitelisting=False)
WhitelistedDomain.objects.create(client=strict, domain_name="allowed.example.com")
WhitelistedIP.objects.create(client=strict, ip_or_cidr="192.0.2.0/24")
```

With the development server running, send requests with `curl`:

```powershell
curl.exe -i http://127.0.0.1:8000/tickets/ -H "Origin: https://allowed.example.com" -H "X-Client-Code: demo-strict"
curl.exe -i http://127.0.0.1:8000/tickets/ -H "Origin: https://blocked.example.com" -H "X-Client-Code: demo-strict"
curl.exe -i http://127.0.0.1:8000/tickets/ -H "Origin: https://unknown.example.com" -H "X-Client-Code: demo-grace"
```

The first request is logged as `PASSED`, the second as `BLOCKED` with HTTP 403,
and the third is logged as `PASSED` while grace mode allows it. Review the
results in Django admin under **Clients > Access attempt logs**, or inspect
them from the shell:

```python
from apps.clients.models import AccessAttemptLog
AccessAttemptLog.objects.values("client__code", "domain", "ip_address", "path", "status")
```