FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app

# Railway persistent volumes are mounted at runtime and can be owned by root.
# Install runuser so we can fix only the volume directory's ownership before
# starting the actual FastAPI process as a non-root user.
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux espeak \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY scripts/build_social_assets.py ./scripts/build_social_assets.py
COPY scripts/build_promo_audio.py ./scripts/build_promo_audio.py
RUN python scripts/build_promo_audio.py --root /app/app/static
# Render a static 1200x630 JPEG preview and correct-size iOS/PWA icons from
# the existing branded game image before dropping build-only Pillow.
RUN pip install --no-cache-dir Pillow \
    && python scripts/build_social_assets.py --root /app/app/static \
    && pip uninstall -y Pillow
RUN groupadd --gid 10001 runner \
    && useradd --create-home --uid 10001 --gid runner runner
COPY --chmod=755 deploy/start-web.sh /usr/local/bin/uno-start

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/uno-start"]
