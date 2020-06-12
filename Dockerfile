FROM ruby:2.5
MAINTAINER "raphael.valyi@akretion.com"

WORKDIR /usr/src/app
COPY . .
RUN addgroup app
RUN adduser app --ingroup=app --disabled-password --quiet --gecos ''
RUN mkdir -p tmp log && chown app:app tmp log

RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential ghostscript git ruby-dev bundler

# throw errors if Gemfile has been modified since Gemfile.lock
RUN bundle config --global frozen 1
RUN bundle install

EXPOSE 9292
USER app
CMD bundle exec puma config.ru
