## Para instalação

Tenha o `docker` e `docker-compose` instalado na máquina

```sh
# No momento, última versão funcional para linux 4.2.6, fazer download em https://rangtecnologia.com.br/downloadsEsus.xhtml
sh build.sh -f eSUS-AB-PEC-4.2.6-Linux64.jar
# Após isso o sistema deve estar funcionando na porta determinada pelo arquivo .env
```

## Known Issues

A versão 4.2.8 está com erro no formulário de cadastro, nas requisições ao banco de dados, pelo endpoint graphql, retorna "Não autorizado"
