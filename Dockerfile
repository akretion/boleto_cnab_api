ARG ALPINE_VERSION=3.24.3
# Pinned by digest: `alpine:3.24` is a moving minor tag, so a rebuild can change
# the base silently. Bump deliberately (update this digest) like a dependency.
ARG ALPINE_DIGEST=sha256:b3413572228e34bd1c9245f5565e6cd127005655e8a7899aef33d8e83255c9e6
FROM alpine:${ALPINE_VERSION}@${ALPINE_DIGEST} AS builder
LABEL org.opencontainers.image.authors="raphael.valyi@akretion.com"

WORKDIR /usr/src/app
COPY Gemfile Gemfile.lock ./

# Gems + their executables go to a self-contained dir (copied wholesale to
# the runtime stage). BUNDLE_PATH also keeps the gem bin dir inside it, so
# no /usr/bin executables need copying.
ENV BUNDLE_PATH=/usr/local/bundle

# Build-only toolchain: compilers (native gems: fast_blank, nio4r,
# rghost_barcode, bigdecimal), ruby headers and git (brcobranca comes from a
# git source). None of these ship in the runtime stage.
#
# Post-install cleanup:
# - bundler runs git-sourced gems (brcobranca) straight from the checkout in
#   bundler/gems/<name>-<rev>/, so the checkout must stay — but its .git
#   history (41MB), docs/ (47MB) and spec/ (1MB) are dead weight at runtime;
#   only lib/ (13MB) is loaded.
RUN apk add --no-cache build-base ruby-dev git \
    && gem install bundler:4.0.19 --no-document \
    && bundle config set --global frozen 1 \
    && bundle install \
    && rm -rf /usr/local/bundle/ruby/*/cache \
          /usr/local/bundle/ruby/*/bundler/gems/*/.git \
          /usr/local/bundle/ruby/*/bundler/gems/*/docs \
          /usr/local/bundle/ruby/*/bundler/gems/*/spec

COPY . .

FROM alpine:3.24.3@sha256:b3413572228e34bd1c9245f5565e6cd127005655e8a7899aef33d8e83255c9e6

# Runtime: only what puma + brcobranca need. ghostscript is used by
# brcobranca at runtime to render PDFs/barcodes. bundler is reinstalled so
# /usr/bin/bundle exists (it is NOT inside BUNDLE_PATH).
# LANG=C.UTF-8: musl has no locale data, and without it Ruby falls back to
# US-ASCII as Encoding.default_external, which is wrong for a boleto service
# that receives "João", "São Paulo" etc.
ENV BUNDLE_PATH=/usr/local/bundle \
    LANG=C.UTF-8 \
     PATH=/usr/local/bundle/bin:$PATH

RUN apk add --no-cache ruby ghostscript \
    && gem install bundler:4.0.19 --no-document \
    # Fixed uid so volume/permission expectations stay stable across rebuilds
    # (`-S` alone picks the first free uid) and match the hardened variants.
    && addgroup -S -g 65532 app \
    && adduser -S -u 65532 -G app app \
    # ghostscript ships the interpreter twice on Alpine: the monolithic
    # /usr/bin/gs (23 MB, what rghost executes) and libgs.so.10.08 (19 MB) plus
    # its only client /usr/bin/gsc. `ldd /usr/bin/gs` shows no libgs and nothing
    # else links against it, so the library is dead weight here. Re-verify with
    # the smoke suite (PDF render) whenever the ghostscript package changes.
    && rm -f /usr/lib/libgs.so.10 /usr/lib/libgs.so.10.08 /usr/bin/gsc \
    # ps2pdf/PDFA wrapper scripts: the service only ever calls `gs` for pdfwrite.
    && rm -rf /usr/share/ghostscript/lib


COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY --from=builder /usr/src/app /usr/src/app

WORKDIR /usr/src/app
RUN mkdir -p tmp log && chown -R app:app /usr/src/app/tmp /usr/src/app/log

EXPOSE 9292
USER app
CMD ["bundle", "exec", "puma", "config.ru"]
