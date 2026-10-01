CREATE DATABASE legacy;
\c legacy
\i /samples/banco_legado.sql
\i /samples/fn_saldo_cliente.sql
\i /samples/sp_atualizar_status_contas_inativas.sql
\i /samples/sp_transferir_entre_contas.sql
\i /samples/sp_processar_lote_taxas.sql
\i /samples/sp_relatorio_mensal_cliente.sql