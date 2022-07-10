FROM ruby:3.1.2-slim
MAINTAINER "raphael.valyi@akretion.com"

WORKDIR /usr/src/app
COPY . .
RUN addgroup app
RUN adduser app --ingroup=app --disabled-password --quiet --gecos ''
RUN mkdir -p tmp log && chown app:app tmp log

RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential ghostscript git ruby-dev bundler

# Evita erro
# Warning: the running version of Bundler (2.1.4) is older than the version that created the lockfile (2.3.7). We suggest you to upgrade to the version that created the lockfile by running `gem install bundler:2.3.7`.
RUN gem install bundler:2.3.7

# throw errors if Gemfile has been modified since Gemfile.lock
RUN bundle config --global frozen 1
RUN bundle install

EXPOSE 9292
USER app
CMD bundle exec puma config.ru
