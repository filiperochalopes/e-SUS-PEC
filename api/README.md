## Verificando mais sobre uma tabela para apromorar API

```sh
docker exec -it esus_psql bash
psql -U postgres
\c esus
\dt
\d+ tb_proced
```

## Encontrando nome da tabela

```sql
select t.table_schema,
       t.table_name
from information_schema.tables t
inner join information_schema.columns c on c.table_name = t.table_name
                                and c.table_schema = t.table_schema
where c.column_name = 'co_principio_ativo'
      and t.table_schema not in ('information_schema', 'pg_catalog')
      and t.table_type = 'BASE TABLE'
order by t.table_schema;
```
