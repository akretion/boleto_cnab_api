FROM akretion/voodoo-ruby:latest

LABEL maintainer "raphael.valyi@akretion.com"

USER root

RUN DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y ghostscript && \
    apt-get clean

ADD . /workspace
RUN bundle install && mkdir -p tmp log && chown ubuntu:ubuntu tmp log
EXPOSE 9292
USER ubuntu

# NOTE uncomment to --bind option to listen outside of the Docker container
CMD bundle exec puma config.ru --bind=tcp://0.0.0.0:9292
