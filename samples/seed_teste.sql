INSERT INTO clientes (id, nome, cpf) VALUES
    (1, 'Ana Teste',   '11111111111'),
    (2, 'Bruno Teste', '22222222222');

INSERT INTO contas (id, cliente_id, agencia, numero, tipo, saldo, status) VALUES
    (1, 1, '0001', '1000-1', 'CORRENTE', 1000.00, 'ATIVA'),
    (2, 1, '0001', '1000-2', 'POUPANCA',  500.00, 'ATIVA'),
    (3, 2, '0001', '2000-1', 'CORRENTE',  250.00, 'ATIVA'),
    (4, 2, '0001', '2000-2', 'SALARIO',    75.00, 'INATIVA'),
    (5, 2, '0001', '2000-3', 'POUPANCA',   10.00, 'ATIVA');

INSERT INTO taxas (tipo_operacao, percentual, valor_minimo, vigente_de, vigente_ate) VALUES
    ('TRANSFERENCIA', 1.5000, 0.50, '2020-01-01', NULL),
    ('SAQUE',         2.0000, 1.00, '2020-01-01', NULL),
    ('DEPOSITO',      0.5000, 0.10, '2020-01-01', '2020-12-31');

INSERT INTO transacoes (id, conta_origem_id, conta_destino_id, tipo, valor) VALUES
    (1, 1,    3,    'TRANSFERENCIA', 200.00),
    (2, 1,    NULL, 'SAQUE',          62.25),
    (3, NULL, 2,    'DEPOSITO',       80.00);

SELECT setval(pg_get_serial_sequence('clientes', 'id'),   (SELECT MAX(id) FROM clientes));
SELECT setval(pg_get_serial_sequence('contas', 'id'),     (SELECT MAX(id) FROM contas));
SELECT setval(pg_get_serial_sequence('transacoes', 'id'), (SELECT MAX(id) FROM transacoes));