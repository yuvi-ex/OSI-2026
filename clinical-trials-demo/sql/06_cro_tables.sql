-- ===================================================================
-- CRO persona tables. Materialised, in their own schema, one row per
-- analysis grain -- the dashboard harness profiles TABLES (it skips views)
-- and computes additive measures, so the grain has to be unambiguous.
--
-- IMPORTANT ON SCOPE: ClinicalTrials.gov has no CRO field. leadSponsor is the
-- pharma company, never the CRO running the work. So these boards describe the
-- MARKET a CRO operates in -- where oncology trials are, who runs them, and how
-- hard they are to execute -- not any one CRO's portfolio.
-- ===================================================================
CREATE SCHEMA IF NOT EXISTS CT_CRO;

-- Screening burden: the count of criteria a patient must be checked against.
-- This exists only because eligibility was chunked; no off-the-shelf trial
-- tracker carries it, and it is the closest thing here to an operational
-- difficulty measure.
CREATE OR REPLACE VIEW CT_CRO.V_BURDEN AS
SELECT NCT_ID,
       COUNT(*)                                                          AS N_CRITERIA,
       SUM(CASE WHEN CRITERION_SECTION='EXCLUSION' THEN 1 ELSE 0 END)    AS N_EXCLUSION,
       SUM(CASE WHEN CRITERION_SECTION='INCLUSION' THEN 1 ELSE 0 END)    AS N_INCLUSION
FROM CT.ELIG_CHUNKS GROUP BY NCT_ID;

-- Enrollment carries registry data-entry artefacts (one trial claims
-- 1,000,000 participants). Winsorise at the 99th percentile so a single typo
-- cannot own a chart, and keep the raw value beside it so nothing is hidden.
CREATE OR REPLACE VIEW CT_CRO.V_ENROL AS
SELECT t.NCT_ID, t.ENROLLMENT AS ENROLLMENT_RAW,
       LEAST(t.ENROLLMENT, (SELECT APPROXIMATE_COUNT_DISTINCT(1) FROM DUAL)*0
             + (SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ENROLLMENT)
                FROM CT.TRIALS)) AS ENROLLMENT
FROM CT.TRIALS t;

-- ---------- GLOBAL: exactly one row per trial ----------
DROP TABLE IF EXISTS CT_CRO.CRO_GLOBAL CASCADE;
CREATE TABLE CT_CRO.CRO_GLOBAL AS
SELECT
  v.NCT_ID                                        AS "Trial ID",
  v.INDICATION                                    AS "Indication",
  v.BRIEF_TITLE                                   AS "Title",
  v.PHASE                                         AS "Phase",
  CASE WHEN v.PHASE_IS_STATED THEN 'Stated' ELSE 'Not stated' END AS "Phase stated",
  v.STATUS_GROUP                                  AS "Status",
  v.LEAD_SPONSOR                                  AS "Sponsor",
  v.SPONSOR_TYPE                                  AS "Sponsor type",
  v.COMPARATOR_DESIGN                             AS "Design",
  COALESCE(v.PRIMARY_ENDPOINT_CATEGORY,'Not recorded') AS "Primary endpoint",
  v.START_YEAR                                    AS "Start year",
  COALESCE(g.REGIONS,0)                           AS "Regions",
  CASE WHEN COALESCE(g.REGIONS,0) > 1 THEN 'Multi-region' ELSE 'Single region' END AS "Footprint",
  COALESCE(g.COUNTRIES,0)                         AS "Countries",
  e.ENROLLMENT                                    AS "Planned enrolment",
  b.N_CRITERIA                                    AS "Criteria",
  b.N_EXCLUSION                                   AS "Exclusion criteria",
  CASE WHEN b.N_CRITERIA >= 40 THEN '4 · Very high'
       WHEN b.N_CRITERIA >= 25 THEN '3 · High'
       WHEN b.N_CRITERIA >= 14 THEN '2 · Moderate'
       ELSE '1 · Light' END                       AS "Screening burden",
  1                                               AS "Trials"
FROM CT.V_LANDSCAPE v
LEFT JOIN CT_CRO.V_BURDEN b ON b.NCT_ID = v.NCT_ID
LEFT JOIN CT_CRO.V_ENROL  e ON e.NCT_ID = v.NCT_ID
LEFT JOIN (SELECT NCT_ID, COUNT(DISTINCT REGION) AS REGIONS,
                  COUNT(DISTINCT COUNTRY) AS COUNTRIES
           FROM CT.V_TRIAL_GEOGRAPHY GROUP BY NCT_ID) g ON g.NCT_ID = v.NCT_ID;

-- ---------- REGIONAL: one row per trial x COUNTRY ----------
-- The grain is country, not region -- a regional head needs to drill to the
-- country, and the region is a rollup of it. So a trial running in 12 countries
-- appears 12 times and "Trials" must always be COUNT(DISTINCT "Trial ID"),
-- never COUNT(*).
--
-- Enrolment is ALLOCATED across the COUNTRIES the trial runs in, matching the
-- grain. Allocating by REGION here was wrong and inflated the total by 57%
-- (3,608,446 against a true 2,293,496) because a trial in 12 countries but 2
-- regions got its enrolment counted six times over.
--
-- 1,059 of the 12,404 trials list no country at all and are therefore ABSENT
-- from this table. Regional totals will never sum to the global board's.
DROP TABLE IF EXISTS CT_CRO.CRO_REGION CASCADE;
CREATE TABLE CT_CRO.CRO_REGION AS
SELECT
  gg.REGION                                       AS "Region",
  gg.COUNTRY                                      AS "Country",
  v.NCT_ID                                        AS "Trial ID",
  v.INDICATION                                    AS "Indication",
  v.BRIEF_TITLE                                   AS "Title",
  v.PHASE                                         AS "Phase",
  v.STATUS_GROUP                                  AS "Status",
  v.LEAD_SPONSOR                                  AS "Sponsor",
  v.SPONSOR_TYPE                                  AS "Sponsor type",
  v.COMPARATOR_DESIGN                             AS "Design",
  v.START_YEAR                                    AS "Start year",
  CASE WHEN r.REGIONS > 1 THEN 'Multi-region' ELSE 'Single region' END AS "Footprint",
  b.N_CRITERIA                                    AS "Criteria",
  b.N_EXCLUSION                                   AS "Exclusion criteria",
  CASE WHEN b.N_CRITERIA >= 40 THEN '4 · Very high'
       WHEN b.N_CRITERIA >= 25 THEN '3 · High'
       WHEN b.N_CRITERIA >= 14 THEN '2 · Moderate'
       ELSE '1 · Light' END                       AS "Screening burden",
  ROUND(e.ENROLLMENT / NULLIF(r.COUNTRIES,0), 1)  AS "Enrolment share",
  e.ENROLLMENT                                    AS "Trial enrolment",
  1                                               AS "Site countries"
FROM CT.V_TRIAL_GEOGRAPHY gg
JOIN CT.V_LANDSCAPE v ON v.NCT_ID = gg.NCT_ID
LEFT JOIN CT_CRO.V_BURDEN b ON b.NCT_ID = v.NCT_ID
LEFT JOIN CT_CRO.V_ENROL  e ON e.NCT_ID = v.NCT_ID
LEFT JOIN (SELECT NCT_ID, COUNT(DISTINCT REGION) AS REGIONS,
                  COUNT(DISTINCT COUNTRY) AS COUNTRIES
           FROM CT.V_TRIAL_GEOGRAPHY GROUP BY NCT_ID) r ON r.NCT_ID = v.NCT_ID;
