FROM alpine:3.24 AS builder
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

FROM alpine:3.24

# Runtime: only what puma + brcobranca need. ghostscript is used by
# brcobranca at runtime to render PDFs/barcodes. bundler is reinstalled so
# /usr/bin/bundle exists (it is NOT inside BUNDLE_PATH).
ENV BUNDLE_PATH=/usr/local/bundle \
    PATH=/usr/local/bundle/bin:$PATH

RUN apk add --no-cache ruby ghostscript \
    && gem install bundler:4.0.19 --no-document \
    && addgroup -S app && adduser -S -G app app

COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY --from=builder /usr/src/app /usr/src/app

WORKDIR /usr/src/app
RUN mkdir -p tmp log && chown -R app:app /usr/src/app/tmp /usr/src/app/log

EXPOSE 9292
USER app
CMD ["bundle", "exec", "puma", "config.ru"]
