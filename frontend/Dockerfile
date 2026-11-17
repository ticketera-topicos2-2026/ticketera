# Frontend image: React + TypeScript + Vite dev server (DS-13, DS-15, DS-17, DS-25).
FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5

# Host user IDs, so files created in mounted folders belong to the host user (DS-13).
ARG UID=1000
ARG GID=1000

# The npm cache lives in /tmp, never in the mounted folder or the home directory.
ENV NPM_CONFIG_CACHE=/tmp/npm-cache \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false

# The base image ships a "node" user with UID and GID 1000; it is replaced by "app" with the host IDs.
RUN deluser --remove-home node \
    && (delgroup node 2> /dev/null || true) \
    && addgroup -g "${GID}" app \
    && adduser -u "${UID}" -G app -D -h /home/app app \
    && mkdir /app \
    && chown app:app /app

USER app
WORKDIR /app

# Dependencies only from the lockfile (DS-25). node_modules stays in the image and Compose keeps it in an anonymous
# volume, so the bind mount of the source code does not hide it (DS-14).
COPY --chown=app:app package.json package-lock.json ./
RUN npm ci && rm -rf /tmp/npm-cache

COPY --chown=app:app . .

EXPOSE 5173
# Host, port and polling come from vite.config.ts.
CMD ["node_modules/.bin/vite"]
