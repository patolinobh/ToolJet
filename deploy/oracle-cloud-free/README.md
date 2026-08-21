# ToolJet CE no Oracle Cloud Always Free — Consulta Veicular Brasil em produção

Roteiro completo para publicar o app **Consulta Veicular Brasil** com **custo zero
permanente**, usando o nível *Always Free* do Oracle Cloud (VM ARM Ampere A1) e o
ToolJet **Community Edition** construído a partir deste fork — que já traz o
template na galeria e **não tem restrição de app público** (a limitação existe
apenas no plano gratuito do ToolJet Cloud).

**Resultado final:** `https://seu-subdominio.duckdns.org` com o app aberto ao
público, HTTPS automático e histórico de consultas persistido.

---

## 1. Conta e VM no Oracle Cloud (~30 min)

1. Crie a conta em <https://www.oracle.com/br/cloud/free/> (pede cartão apenas
   para verificação; recursos *Always Free* não geram cobrança).
2. Menu **Compute → Instances → Create instance**:
   - **Image**: Ubuntu 22.04 (aarch64/ARM);
   - **Shape**: *Ampere* → **VM.Standard.A1.Flex** com **4 OCPUs e 24 GB de RAM**
     (o teto do Always Free — use tudo);
   - **Boot volume**: 100 GB (o gratuito soma até 200 GB);
   - Adicione sua **chave SSH pública** e crie.
   - ⚠️ Se aparecer *"Out of capacity"* para A1, tente outro *Availability
     Domain* ou outra região na criação da conta (São Paulo esgota com
     frequência; us-ashburn costuma ter vaga) — ou repita mais tarde.
3. Anote o **IP público** da instância.

## 2. Liberar as portas 80 e 443

O Oracle bloqueia em **duas camadas** — libere as duas:

**a) Console web** — VCN da instância → **Security List** da subnet → *Add
Ingress Rules*: origem `0.0.0.0/0`, protocolo TCP, portas `80` e `443` (uma
regra para cada).

**b) Dentro da VM** (a imagem Ubuntu da Oracle traz iptables restritivo):

```bash
ssh ubuntu@IP_PUBLICO
sudo iptables -I INPUT 5 -p tcp --dport 80  -j ACCEPT
sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 3. Docker e código

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && newgrp docker

git clone https://github.com/patolinobh/ToolJet.git
cd ToolJet/deploy/oracle-cloud-free
```

## 4. Domínio gratuito (DuckDNS)

1. Entre em <https://www.duckdns.org> (login com Google/GitHub);
2. Crie um subdomínio (ex.: `consulta-veicular`) e aponte-o para o **IP público**
   da VM;
3. O Caddy emitirá o certificado HTTPS (Let's Encrypt) sozinho no primeiro acesso.

## 5. Configurar e subir

```bash
cp env.example .env
nano .env    # domínio + segredos (gere com os comandos abaixo) + senha do banco
openssl rand -hex 32   # → LOCKBOX_MASTER_KEY e PGRST_JWT_SECRET (gere um para cada)
openssl rand -hex 64   # → SECRET_KEY_BASE

docker compose up -d --build
```

O primeiro build compila o fork na VM ARM (~15–25 min). Acompanhe com
`docker compose logs -f tooljet` até ver o servidor de pé; depois acesse
`https://SEU-SUBDOMINIO.duckdns.org` e conclua o cadastro do administrador.

## 6. Publicar o app Consulta Veicular

1. **Create new app → Templates** → o template **"Consulta veicular Brasil"** já
   está na galeria (vem embutido neste fork) → crie o app;
2. **Workspace settings → Workspace constants**:
   - `PLACA_API_URL` = `https://wdapi2.com.br/consulta/{placa}/SUA_CHAVE`
     (consulta real por placa — cota gratuita do wdapi2);
   - `FIPE_API_TOKEN` = chave gratuita da Parallelum (opcional — habilita o
     gráfico com histórico oficial de valores);
3. Abra o app e teste uma consulta (placa real e um chassi);
4. Clique em **Release** (canto superior direito do editor);
5. **Share → Make application public** → copie o link público. Pronto! 🚗

## 7. Operação

```bash
# Logs
docker compose logs -f tooljet

# Backup diário do banco (agende no cron)
docker compose exec postgres pg_dumpall -U postgres | gzip > backup_$(date +%F).sql.gz

# Atualizar o app após novos commits no fork
git pull && docker compose up -d --build
```

**Avisos:**

- Com o app público, a **cota do wdapi2 é consumida por qualquer visitante** —
  monitore o painel deles e considere o plano pago (ou um agregador da Fase 2)
  quando houver tráfego;
- O laudo em PDF, o histórico no ToolJet Database e todos os modos de consulta
  funcionam idênticos ao validado em desenvolvimento — é o mesmo código;
- Snapshot/backup da VM: o Always Free não expira, mas trate o servidor como
  qualquer produção (backups fora da máquina).
