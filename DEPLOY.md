# Deploying Cognify to AWS (single EC2 instance + custom domain)

This deploys all services (FastAPI backend, Streamlit frontend, Redis, ChromaDB,
embedding service) via `docker compose` on one EC2 instance, fronted by
host-level Nginx doing TLS termination for your domain.

## 1. Launch the EC2 instance
- AMI: Ubuntu 22.04 LTS
- Instance type: `t3.medium` or larger (embedding model + Chroma need real memory; `t3.small` will struggle)
- Storage: 20GB+ gp3 volume
- Security group: allow inbound `22` (SSH, ideally restricted to your IP), `80`, `443`. Do **not** open 6379/8000/8003/8005/8501 — those stay internal, proxied through Nginx.
- Allocate and associate an Elastic IP so the address doesn't change on reboot.

## 2. Point your domain at the instance
At your domain registrar's DNS settings, add:
- `A` record: `@` → the Elastic IP
- `A` record: `www` → the Elastic IP

DNS propagation can take a few minutes to a few hours.

## 3. Install Docker + Nginx + Certbot on the instance
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg nginx certbot python3-certbot-nginx

# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

## 4. Clone the repo and configure environment
```bash
git clone https://github.com/meumarkhan/Cognify-RAG-based-Knowledge-Chatbot.git
cd Cognify-RAG-based-Knowledge-Chatbot
cp .env.example .env
nano .env   # fill in GROQ_API_KEY, REDIS_PASSWORD, ALLOWED_ORIGINS=https://YOUR_DOMAIN
```

## 5. Start the app
```bash
docker compose up -d --build
docker compose ps   # confirm all 5 services are healthy
```

Backend listens on `127.0.0.1:8000`, frontend on `127.0.0.1:8501` — both internal
only, matching `docker-compose.yml`.

## 6. Configure Nginx
```bash
sudo cp nginx/cognify.conf /etc/nginx/sites-available/cognify.conf
sudo sed -i 's/YOUR_DOMAIN/yourdomain.com/g' /etc/nginx/sites-available/cognify.conf
sudo ln -s /etc/nginx/sites-available/cognify.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 7. Enable HTTPS
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```
Certbot edits the Nginx config to add the TLS server block and sets up a
renewal timer automatically (`systemctl status certbot.timer`).

## 8. Verify
```bash
curl -I https://yourdomain.com
curl https://yourdomain.com/api/v1/
```
Open `https://yourdomain.com` in a browser, upload a small PDF, ask a question,
confirm you get an answer back.

## Updating the deployment
```bash
cd Cognify-RAG-based-Knowledge-Chatbot
git pull
docker compose up -d --build
```

## Notes
- Redis and ChromaDB data persist in the `redis-data` Docker volume and the
  `./chroma` bind mount respectively — back these up if you care about the
  ingested documents/chat history surviving a host loss.
- `CHROMA_ALLOW_RESET` should stay `FALSE` in production (`.env.example`
  default) since the reset endpoint wipes the whole vector collection.
