# marcujump — "Markus im Weltall" HTML game served by nginx.
# The game is fetched from GitHub at build time so every build ships the
# current HEAD of https://github.com/refap3/marcujump.
FROM alpine/git:latest AS fetch
# MARCUJUMP_SHA is passed by install.sh/update.sh (remote HEAD commit) purely
# to bust the Docker build cache when upstream changes.
ARG MARCUJUMP_SHA=unknown
RUN git clone --depth 1 https://github.com/refap3/marcujump.git /src \
    && echo "built from commit: ${MARCUJUMP_SHA}"

FROM nginx:alpine
COPY --from=fetch /src/index.html /src/MarcuJumpGuide.html /usr/share/nginx/html/
