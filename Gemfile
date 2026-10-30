source 'https://rubygems.org'

# A gem BRCobranca vem do repositório AGREGADO em vendor/brcobranca, gerado
# por gitaggregate.yaml (acsone/git-aggregator) a partir de:
#   - upstream  https://github.com/kivanio/brcobranca.git  branch master
#   - fork      https://github.com/akretion/brcobranca.git branch IMP-split_payment_ibs_cbs
# Regenerar com: gitaggregate -c gitaggregate.yaml
# Ver docs/AGREGACAO_BRCOBRANCA.md.
gem 'brcobranca', path: 'vendor/brcobranca'

gem 'grape'
gem 'grape-swagger'
gem 'puma'
gem 'base64'
gem 'mutex_m'
gem 'bigdecimal'
# A versão 0.9.9 publicada no rubygems está quebrada (https://github.com/shairontoledo/rghost/issues/75);
# o BRCobranca fixa a dependência em rghost = 0.9.8 (última versão publicada que funciona).
gem 'rghost', '0.9.8'
