# Deploying wikigraph to Wikimedia Toolforge

Deploy wikigraph as a **build service** container on Toolforge using Cloud Native Buildpacks.

## Prerequisites

- A [Toolforge account](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Quickstart) with SSH access
- The tool name registered (e.g. `wikigraph`) via [toolsadmin](https://toolsadmin.wikimedia.org/)
- A fork or clone of this repo pushed to a public Git repository

## One-time Setup

### 1. Create the service template

SSH to the bastion and write `$HOME/service.template`:

```bash
ssh <username>@login.toolforge.org
become wikigraph
```

```yaml
# /data/project/wikigraph/service.template
cpu: 500m
mem: 1Gi
type: buildservice
mount: none
health-check-path: /
```

1Gi memory is recommended because spaCy + graph assembly needs more than the default 512Mi.

### 2. Build and start

Build the container image directly from your public Git repo:

```bash
toolforge build start https://github.com/<your-username>/wikigraph
```

Watch the build log:
```bash
toolforge build logs --follow
```

Once the build succeeds, start the webservice:
```bash
toolforge webservice --template=$HOME/service.template start
```

Your tool is now live at **https://wikigraph.toolforge.org**.

### 3. Set environment variables

```bash
toolforge envvars set WIKI_USER_AGENT="wikigraph/0.1.0 (https://github.com/fuzheado/wikigraph; your-email@example.com)"
```

The User-Agent is required by Wikimedia API policy. You can also set `WIKI_MAX_CONCURRENT`, `WIKI_CACHE_DIR`, etc. (see `.env.example`).

## Updating

```bash
become wikigraph
toolforge build start https://github.com/<your-username>/wikigraph
toolforge webservice restart
```

The build service pulls the latest code from the repo, rebuilds the image, then a restart picks it up.

## Logs

```bash
toolforge webservice logs         # recent logs
toolforge webservice logs -f      # follow in real-time
```

## Local testing with Docker

You can test the container locally before deploying:

```bash
docker build -t wikigraph .
docker run --rm -p 8000:8000 -e WIKI_USER_AGENT="wikigraph/0.1.0 (local test; your-email@example.com)" wikigraph
```

Then open http://localhost:8000.

## Troubleshooting

| Symptom | Likely fix |
|---------|-----------|
| Pod crashes on start | Check logs: `toolforge webservice logs`. Common cause: out of memory — bump `mem: 1Gi` in `service.template` |
| Build fails | `toolforge build logs --follow` to see where it failed. Common cause: network timeout downloading spaCy model — retry the build |
| "No data for this date" in UI | The Hatnote API may not have data for that date yet, or the date format is wrong |
| 502 Bad Gateway | The container may be taking too long to start. Check `toolforge webservice status` and logs |
| Rate-limited by MW API | Set `WIKI_MAX_CONCURRENT=2` and a proper `WIKI_USER_AGENT` with your contact email |
