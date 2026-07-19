# Oracle Cloud Deployment

## Recommended shape

- `VM.Standard.A1.Flex`
- 2 OCPUs
- 12 GB RAM
- Ubuntu ARM64
- 50–100 GB boot volume

Do not use a 1 GB micro instance for this combined scheduler, media renderer, FFmpeg, API, Caddy, and Docker workload.

## OCI network rules

Add ingress rules to the subnet security list or Network Security Group:

| Source | Protocol | Port | Purpose |
|---|---|---:|---|
| Your IP/32 preferred | TCP | 22 | SSH administration |
| 0.0.0.0/0 | TCP | 80 | ACME redirect/challenge |
| 0.0.0.0/0 | TCP | 443 | HTTPS API/media |

Do not open ports 8080 or database ports publicly.

## Deployment

```bash
ssh -i key.pem ubuntu@PUBLIC_IP
git clone REPOSITORY_URL /tmp/cryptopulse-source
sudo bash /tmp/cryptopulse-source/cryptopulse_ai/scripts/bootstrap_oci.sh
exit
```

Log in again and deploy:

```bash
ssh -i key.pem ubuntu@PUBLIC_IP
bash /tmp/cryptopulse-source/cryptopulse_ai/scripts/deploy_oci.sh REPOSITORY_URL main
cd /opt/cryptopulse/cryptopulse_ai
nano .env
docker compose up -d --build
docker compose logs -f app
```

## OCI capacity errors

If A1 reports insufficient host capacity, try another availability domain when available. OCI Always Free capacity is not guaranteed in every domain at every moment.

## Recovery

```bash
cd /opt/cryptopulse/cryptopulse_ai
docker compose ps
docker compose logs --since=30m app
git log --oneline -10
bash /opt/cryptopulse/cryptopulse_ai/scripts/rollback.sh COMMIT_SHA
```
