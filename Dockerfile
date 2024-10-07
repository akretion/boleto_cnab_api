FROM alpine:latest
LABEL org.opencontainers.image.authors="raphael.valyi@akretion.com"

WORKDIR /usr/src/app
COPY . .
RUN addgroup -S app && adduser -S -G app app && \
    mkdir -p tmp log && chown app:app tmp log

RUN set -eux; \
        apk update && \
        apk upgrade && \
        apk add --no-cache \
           build-base \
           ghostscript \
           git \
           ruby-dev \
        && rm -rf /var/cache/apk/* \
        ;

RUN set -eux; \
   gem install bundler:2.5.11 --no-document \
   && bundle install \
   && rm -rf /usr/local/bundle/cache/*.gem \
   ;

# throw errors if Gemfile has been modified since Gemfile.lock
RUN bundle config --global frozen 1 && bundle install

EXPOSE 9292
USER app
CMD ["bundle", "exec", "puma", "config.ru"]
