# Loki image with a healthcheck tool (change e1-request-log, design RL-17; Req local-environment: Every container
# reports its health).
#
# The official Loki image is distroless: no shell, no HTTP client and no health subcommand, so it cannot run a
# healthcheck. This image adds only the static BusyBox binary, called as "busybox wget" by the healthcheck in
# docker-compose.yml; no applet is linked into PATH and nothing else changes. Both images are pinned by index digest
# (DS-25). It keeps Loki's user (10001) and its /loki directory, owned by that user, so the named volume mounted
# there is writable.
FROM busybox:1.37-musl@sha256:f6a95d611e0a8780fabdb2aec43e31275b2720dfefa3e41b16835bfc42454478 AS busybox

FROM grafana/loki:3.7.10@sha256:b43c257ccfc925d4a50b8717cac61a3b51df8c48d01847936057e5c4075a24a7

COPY --from=busybox /bin/busybox /usr/local/bin/busybox
