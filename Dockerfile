FROM node:22-bookworm-slim AS mermaid-runtime

ENV PUPPETEER_SKIP_DOWNLOAD=true

RUN npm install --prefix /opt/mermaid @mermaid-js/mermaid-cli@11.16.0


FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

COPY --from=mermaid-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=mermaid-runtime /opt/mermaid /opt/mermaid

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        libreoffice-impress \
        poppler-utils \
    && ln -s /opt/mermaid/node_modules/.bin/mmdc /usr/local/bin/mmdc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace
RUN python -m pip install --no-cache-dir -e ".[dev]"

CMD ["pytest"]
