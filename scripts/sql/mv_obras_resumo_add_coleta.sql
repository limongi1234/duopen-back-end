-- ─────────────────────────────────────────────────────────────────────────────
-- Recria mv_obras_resumo incluindo as 4 colunas de coleta (PRs #5/#9):
--   cnpj_executora, num_contrato, num_licitacao, ano_conclusao
-- (percentual_executado_financeiro já estava na view).
--
-- Materialized view não aceita ALTER ADD COLUMN nem CREATE OR REPLACE -> DROP+CREATE.
-- O CREATE já popula (WITH DATA por padrão), então não precisa REFRESH em seguida.
--
-- ⚠️ Índices: o DROP remove os índices da view. Se houver índices customizados em
-- mv_obras_resumo, recrie-os após o CREATE (veja sugestão no fim).
-- ─────────────────────────────────────────────────────────────────────────────

DROP MATERIALIZED VIEW IF EXISTS mv_obras_resumo;

CREATE MATERIALIZED VIEW mv_obras_resumo AS
 SELECT o.id,
    o.nome,
    o.objeto,
    o.tipo,
    o.situacao,
    o.secretaria,
    o.bairro,
    o.municipio,
    o.latitude,
    o.longitude,
    o.percentual_executado,
    o.percentual_executado_financeiro,
    o.cnpj_executora,        -- novo (#5)
    o.num_contrato,          -- novo (#5)
    o.num_licitacao,         -- novo (#5)
    o.ano_conclusao,         -- novo (#9)
    o.dias_atraso,
    o.valor_contrato,
    o.valor_aditivos,
    o.valor_final,
    o.area_m2,
    o.data_inicio,
    o.data_prevista_fim,
    o.data_conclusao,
    o.ieop_score,
    o.ieop_classe,
    o.ieop_custo,
    o.ieop_atraso,
    o.ieop_recorrencia,
    o.ieop_execucao,
    o.ieop_calculado_em,
    p.prob_atraso,
    p.prob_estouro,
    p.nivel_risco,
    p.modelo_versao,
    p.atualizado_em AS predicao_atualizada_em,
    count(a.id) AS qtd_aditivos,
    COALESCE(sum(a.valor), 0::numeric) AS valor_total_aditivos,
    o.fonte_origem,
    o.criado_em,
    o.atualizado_em
   FROM obras o
     LEFT JOIN predicoes p ON p.id_obra = o.id
     LEFT JOIN contratos c ON c.id_obra = o.id
     LEFT JOIN aditivos a ON a.id_contrato = c.id
  GROUP BY o.id, o.nome, o.objeto, o.tipo, o.situacao, o.secretaria, o.bairro,
           o.municipio, o.latitude, o.longitude, o.percentual_executado,
           o.percentual_executado_financeiro, o.cnpj_executora, o.num_contrato,
           o.num_licitacao, o.ano_conclusao, o.dias_atraso, o.valor_contrato,
           o.valor_aditivos, o.valor_final, o.area_m2, o.data_inicio,
           o.data_prevista_fim, o.data_conclusao, o.ieop_score, o.ieop_classe,
           o.ieop_custo, o.ieop_atraso, o.ieop_recorrencia, o.ieop_execucao,
           o.ieop_calculado_em, p.prob_atraso, p.prob_estouro, p.nivel_risco,
           p.modelo_versao, p.atualizado_em, o.fonte_origem, o.criado_em,
           o.atualizado_em;

-- (Opcional) índice único em id -> permite REFRESH MATERIALIZED VIEW CONCURRENTLY:
-- CREATE UNIQUE INDEX IF NOT EXISTS mv_obras_resumo_id_idx ON mv_obras_resumo (id);
