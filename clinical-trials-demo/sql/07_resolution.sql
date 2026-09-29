-- ===================================================================
-- RESOLUTION LAYER — the judgements a landscape question depends on,
-- written down as data instead of buried in a WHERE clause.
--
-- Three questions have no single right answer, so the layer publishes the
-- alternatives and picks a default rather than pretending the choice was
-- obvious:
--   which trials count as "pembrolizumab"   -> DRUG_ALIAS, V_TRIAL_DRUG
--   which sponsors are the same company     -> V_SPONSOR
--   what "in the US" means                  -> GEO_DEFINITION, V_TRIAL_GEO
-- ===================================================================

-- ---------------------------------------------------------------- drugs
-- CURATED, not derived. ClinicalTrials.gov has no controlled vocabulary for
-- intervention names, so brand names and development codes are only linked to
-- a generic name if somebody says so. Measured on this corpus: searching
-- "pembrolizumab" alone misses 28 trials that say only Keytruda or MK-3475.
DROP TABLE IF EXISTS CT.DRUG_ALIAS CASCADE;
CREATE TABLE CT.DRUG_ALIAS (CANONICAL VARCHAR(80), ALIAS VARCHAR(80), ALIAS_KIND VARCHAR(20));
INSERT INTO CT.DRUG_ALIAS VALUES
  ('pembrolizumab','pembrolizumab','generic'), ('pembrolizumab','keytruda','brand'),
  ('pembrolizumab','mk-3475','code'),          ('pembrolizumab','mk3475','code'),
  ('pembrolizumab','sch 900475','code'),       ('pembrolizumab','sch900475','code'),
  ('pembrolizumab','lambrolizumab','former'),
  ('nivolumab','nivolumab','generic'),         ('nivolumab','opdivo','brand'),
  ('nivolumab','bms-936558','code'),
  ('atezolizumab','atezolizumab','generic'),   ('atezolizumab','tecentriq','brand'),
  ('durvalumab','durvalumab','generic'),       ('durvalumab','imfinzi','brand'),
  ('trastuzumab','trastuzumab','generic'),     ('trastuzumab','herceptin','brand'),
  ('osimertinib','osimertinib','generic'),     ('osimertinib','tagrisso','brand'),
  ('osimertinib','azd9291','code');

-- One row per trial per canonical drug, recording HOW it matched so the
-- alias-only hits can be shown separately.
CREATE OR REPLACE VIEW CT.V_TRIAL_DRUG AS
SELECT DISTINCT i.NCT_ID, a.CANONICAL AS DRUG, a.ALIAS_KIND, i.INTERVENTION_NAME AS MATCHED_TEXT
FROM CT.TRIAL_INTERVENTIONS i
JOIN CT.DRUG_ALIAS a ON UPPER(i.INTERVENTION_NAME) LIKE '%' || UPPER(a.ALIAS) || '%';

-- Combination vs monotherapy. A judgement, not a fact: this counts DRUG and
-- BIOLOGICAL interventions on the trial. A trial testing a backbone plus a new
-- agent is a combination by this rule even if the backbone is incidental.
CREATE OR REPLACE VIEW CT.V_TRIAL_REGIMEN AS
SELECT NCT_ID,
       COUNT(DISTINCT INTERVENTION_NAME) AS N_AGENTS,
       CASE WHEN COUNT(DISTINCT INTERVENTION_NAME) = 1 THEN TRUE ELSE FALSE END AS IS_MONOTHERAPY
FROM CT.TRIAL_INTERVENTIONS
WHERE INTERVENTION_TYPE IN ('DRUG','BIOLOGICAL')
GROUP BY NCT_ID;

-- ---------------------------------------------------------------- sponsors
-- Two different companies share the name "Merck". Rolling up on a LIKE would
-- merge a German competitor into the originator's count; matching exactly would
-- drop three subsidiaries that genuinely are Merck & Co. Both are wrong, so the
-- rule is explicit: strip a trailing "a subsidiary of X", then apply exceptions.
CREATE OR REPLACE VIEW CT.V_SPONSOR AS
SELECT t.NCT_ID, t.LEAD_SPONSOR, t.SPONSOR_TYPE,
       CASE
         WHEN UPPER(t.LEAD_SPONSOR) LIKE '%MERCK KGAA%'          THEN 'Merck KGaA (Darmstadt)'
         WHEN UPPER(t.LEAD_SPONSOR) LIKE '%MERCK SHARP%'
           OR UPPER(t.LEAD_SPONSOR) LIKE '%MERCK & CO%'          THEN 'Merck & Co.'
         WHEN UPPER(t.LEAD_SPONSOR) LIKE '%SUBSIDIARY OF PFIZER%' THEN 'Pfizer'
         WHEN INSTR(UPPER(t.LEAD_SPONSOR), 'SUBSIDIARY OF ') > 0
           THEN TRIM(SUBSTR(t.LEAD_SPONSOR,
                INSTR(UPPER(t.LEAD_SPONSOR), 'SUBSIDIARY OF ') + 14))
         ELSE t.LEAD_SPONSOR
       END AS SPONSOR_GROUP
FROM CT.V_LANDSCAPE t;

-- ---------------------------------------------------------------- geography
-- "In the US" has three readings and they do not agree. The layer states all
-- three, says which is the default, and says which one the registry cannot
-- answer at all.
DROP TABLE IF EXISTS CT.GEO_DEFINITION CASCADE;
CREATE TABLE CT.GEO_DEFINITION (DEFINITION VARCHAR(40), RULE_TEXT VARCHAR(200),
                                IS_DEFAULT BOOLEAN, IS_AVAILABLE BOOLEAN, NOTE VARCHAR(300));
INSERT INTO CT.GEO_DEFINITION VALUES
  ('has_us_site', 'at least one recruiting site in the United States', TRUE, TRUE,
   'The default. Broadest reading, and the one a feasibility question usually means.'),
  ('us_only', 'every recorded site is in the United States', FALSE, TRUE,
   'Much narrower. On pembrolizumab this is 298 against 527 - a 43% difference on the same question.'),
  ('us_led', 'the lead sponsor is a US organisation', FALSE, FALSE,
   'NOT DERIVABLE. ClinicalTrials.gov does not publish sponsor country, so this cannot be computed from the registry. Inferring it from the sponsor name would be a guess.');

CREATE OR REPLACE VIEW CT.V_TRIAL_GEO AS
SELECT t.NCT_ID,
       COUNT(DISTINCT g.COUNTRY) AS N_COUNTRIES,
       MAX(CASE WHEN g.COUNTRY = 'United States' THEN 1 ELSE 0 END) = 1 AS HAS_US_SITE,
       (COUNT(DISTINCT g.COUNTRY) = 1
        AND MAX(CASE WHEN g.COUNTRY = 'United States' THEN 1 ELSE 0 END) = 1) AS US_ONLY
FROM CT.V_LANDSCAPE t
LEFT JOIN CT.TRIAL_COUNTRIES g ON g.NCT_ID = t.NCT_ID
GROUP BY t.NCT_ID;

-- ---------------------------------------------------------------- one view
CREATE OR REPLACE VIEW CT.V_TRIAL_RESOLVED AS
SELECT t.*, s.SPONSOR_GROUP,
       g.N_COUNTRIES, g.HAS_US_SITE, g.US_ONLY,
       r.N_AGENTS, r.IS_MONOTHERAPY
FROM CT.V_LANDSCAPE t
LEFT JOIN CT.V_SPONSOR      s ON s.NCT_ID = t.NCT_ID
LEFT JOIN CT.V_TRIAL_GEO    g ON g.NCT_ID = t.NCT_ID
LEFT JOIN CT.V_TRIAL_REGIMEN r ON r.NCT_ID = t.NCT_ID;
