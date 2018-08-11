FROM ruby:2.5.1-alpine3.7
MAINTAINER "raphael.valyi@akretion.com"

WORKDIR /usr/src/app
COPY . .
RUN addgroup -S app && adduser -S -G app app
RUN mkdir -p tmp log && chown app:app tmp log

RUN apk add build-base ghostscript git

# throw errors if Gemfile has been modified since Gemfile.lock
RUN bundle config --global frozen 1
RUN bundle install
RUN apk del build-base git

EXPOSE 9292
USER app
CMD bundle exec puma config.ru
